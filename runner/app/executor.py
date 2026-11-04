"""Runs one submission: [compile in one container], run the judge in another, read the verdict.

Blocking code (docker-py): the HTTP layer calls it through a thread. Every container is removed
in `finally`, before the caller gives its concurrency slot back, so the number of sandbox
containers never exceeds RUNNER_MAX_CONCURRENCY.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass

import docker
import requests

from app import protocol, spec
from app.config import Settings
from app.schemas import RunRequest

logger = logging.getLogger(__name__)

# a bit over what the judge itself allows, so that the judge's own answer wins the race
COMPILE_DEADLINE_S = spec.COMPILE_SECONDS + 10
STDOUT_LIMIT = 24 * spec.MIB  # a binary comes back through stdout
DOCKER_ERRORS = (docker.errors.DockerException, requests.RequestException, OSError)


class SandboxError(Exception):
    """Docker or the judge failed; this says nothing about the user's code."""


@dataclass
class ExecResult:
    stdout: bytes
    stderr: bytes
    timed_out: bool
    oom_killed: bool
    exit_code: int | None


def _first_json_line(data: bytes) -> tuple[dict | None, bytes]:
    head, _, rest = data.partition(b"\n")
    try:
        value = json.loads(head)
    except ValueError:
        return None, b""
    return (value if isinstance(value, dict) else None), rest


class Sandbox:
    def __init__(self, client: docker.DockerClient, settings: Settings):
        self.client = client
        self.settings = settings

    # --- the one primitive: a locked-down container fed through stdin ----------------------

    def _exec(
        self, *, image: str, command: list[str], files: list[tuple[str, bytes, int]],
        mem_bytes: int, nofile: int, deadline_s: float,
    ) -> ExecResult:
        api = self.client.api
        options = spec.container_options(
            image=image, command=command, name=f"cb-sb-{uuid.uuid4().hex[:12]}",
            mem_bytes=mem_bytes, cpus=self.settings.SANDBOX_CPUS, nofile=nofile,
        )
        archive = protocol.build_tar(files)
        container_id = None
        sock = None
        try:
            container_id = api.create_container(
                **options.create, host_config=api.create_host_config(**options.host)
            )["Id"]
            sock = api.attach_socket(
                container_id, params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
            )
            raw = getattr(sock, "_sock", sock)
            api.start(container_id)

            deadline = time.monotonic() + deadline_s
            frames = protocol.Frames(STDOUT_LIMIT)
            protocol.send_all(raw, archive, deadline)
            finished = protocol.read_until_closed(raw, frames, deadline)

            if not finished:
                _quiet(api.kill, container_id)
            exit_code = oom_killed = None
            try:
                exit_code = api.wait(container_id, timeout=10).get("StatusCode")
                oom_killed = api.inspect_container(container_id)["State"].get("OOMKilled", False)
            except DOCKER_ERRORS:
                _quiet(api.kill, container_id)
            return ExecResult(
                stdout=bytes(frames.out), stderr=bytes(frames.err), timed_out=not finished,
                oom_killed=bool(oom_killed), exit_code=exit_code,
            )
        except DOCKER_ERRORS as exc:
            raise SandboxError(f"docker: {type(exc).__name__}: {exc}") from exc
        finally:
            if sock is not None:
                _quiet(sock.close)
            if container_id is not None:
                _quiet(api.remove_container, container_id, force=True)

    # --- steps -------------------------------------------------------------------------------

    def _compile(self, code: bytes) -> tuple[bytes | None, str]:
        """(binary, "") or (None, compiler message)."""
        res = self._exec(
            image=self.settings.SANDBOX_CPP_IMAGE, command=["compile"],
            files=[("main.cpp", code, 0o644)],
            mem_bytes=spec.COMPILE_MEMORY_MB * spec.MIB, nofile=256, deadline_s=COMPILE_DEADLINE_S,
        )
        header, binary = _first_json_line(res.stdout)
        if header is None:
            if res.timed_out:
                return None, f"Compilation timed out after {spec.COMPILE_SECONDS} s"
            if res.oom_killed:
                return None, "The compiler ran out of memory"
            raise SandboxError(f"compile container gave no answer (exit {res.exit_code}): {res.stderr[:300]!r}")
        if header.get("verdict") == "ERROR":
            raise SandboxError(f"judge: {header.get('reason')}")
        if not header.get("ok"):
            return None, str(header.get("log", ""))[:2048]
        if len(binary) != header.get("size"):
            raise SandboxError("compiled binary arrived incomplete")
        return binary, ""

    def judge(self, request: RunRequest) -> dict:
        """The judge's answer as a dict (verdict, passed, total, failed_index, ...), or
        {"verdict": "CE", "compile_log": ...}. Raises SandboxError when it cannot say."""
        tests = [*request.tests.public, *request.tests.hidden]
        code = request.code.encode("utf-8", errors="replace")
        time_ms = spec.time_limit_ms(request.time_limit_ms)
        mem_mb = spec.memory_limit_mb(request.memory_limit_mb)

        if request.language == "python":
            image, program = self.settings.SANDBOX_PYTHON_IMAGE, ("solution.py", code, 0o644)
        else:
            binary, log = self._compile(code)
            if binary is None:
                return {"verdict": "CE", "compile_log": log}
            image, program = self.settings.SANDBOX_CPP_IMAGE, ("main", binary, 0o755)

        job = {
            "language": request.language, "count": len(tests), "time_limit_ms": time_ms,
            "total_budget_ms": spec.JUDGE_TOTAL_MS, "memory_limit_bytes": mem_mb * spec.MIB,
        }
        files = [program, ("job.json", json.dumps(job).encode(), 0o644)]
        for index, test in enumerate(tests):
            files.append((f"in/{index}", test.input.encode("utf-8", errors="replace"), 0o644))
            files.append((f"out/{index}", test.output.encode("utf-8", errors="replace"), 0o644))

        res = self._exec(
            image=image, command=["run"], files=files, mem_bytes=mem_mb * spec.MIB,
            nofile=64, deadline_s=spec.RUN_TOTAL_SECONDS,
        )
        answer, _ = _first_json_line(res.stdout)
        if answer is None:
            # The judge died or never answered. The user's program can do that to it (kill it,
            # eat all the memory, run out the clock), so these are verdicts, not server errors.
            if res.timed_out:
                return {"verdict": "TLE", "passed": 0, "total": len(tests), "failed_index": None,
                        "time_ms": spec.RUN_TOTAL_SECONDS * 1000, "memory_kb": 0, "detail": None}
            if res.oom_killed:
                return {"verdict": "MLE", "passed": 0, "total": len(tests), "failed_index": None,
                        "time_ms": 0, "memory_kb": mem_mb * 1024, "detail": None}
            if res.exit_code is not None and res.exit_code >= 128:
                # killed by a signal and nothing else is to blame: a program that kills its parent
                # (the judge) gets a runtime error, not a free "sandbox is down"
                logger.warning("Judge was killed from inside (exit %s)", res.exit_code)
                return {"verdict": "RE", "passed": 0, "total": len(tests), "failed_index": None,
                        "time_ms": 0, "memory_kb": 0, "detail": None}
            raise SandboxError(f"judge gave no answer (exit {res.exit_code}): {res.stderr[:300]!r}")
        if answer.get("verdict") == "ERROR":
            raise SandboxError(f"judge: {answer.get('reason')}")
        return answer

    # --- health ------------------------------------------------------------------------------

    def check(self) -> dict[str, str]:
        """Docker answers and both images are there. Values are "ok" or "error"."""
        checks = {}
        try:
            checks["docker"] = "ok" if self.client.api.ping() else "error"
        except DOCKER_ERRORS:
            checks["docker"] = "error"
        for key, image in (("image_python", self.settings.SANDBOX_PYTHON_IMAGE),
                           ("image_cpp", self.settings.SANDBOX_CPP_IMAGE)):
            try:
                self.client.api.inspect_image(image)
                checks[key] = "ok"
            except DOCKER_ERRORS:
                checks[key] = "error"
        return checks


def _quiet(func, *args, **kwargs) -> None:
    try:
        func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - clean-up must not hide the real result
        logger.debug("clean-up step failed: %s", type(exc).__name__)


def make_client(settings: Settings) -> docker.DockerClient:
    # base_url given explicitly: the environment is never consulted for where Docker is
    return docker.DockerClient(
        base_url=settings.SANDBOX_DOCKER_URL, version=settings.SANDBOX_DOCKER_API_VERSION,
        timeout=30, max_pool_size=64,
    )
