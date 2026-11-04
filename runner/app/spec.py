"""The container spec. Every option that makes the sandbox a sandbox is written here, in code.
Nothing in a request can change it: the client sends a language, the code and the tests.

The socket proxy filters endpoints, not bodies (a create with Privileged or Binds would pass it),
which is why the runner is the only place that builds a spec and why this module is tiny.
"""

from dataclasses import dataclass

from docker.types import LogConfig, Ulimit

MIB = 1 << 20

SANDBOX_UID = 10001
LABEL = {"cb.sandbox": "1"}  # the reaper looks for this

# time per test (ms): the task's limit, 2 s without one, never above 10 s
DEFAULT_TIME_LIMIT_MS = 2000
MIN_TIME_LIMIT_MS = 100
MAX_TIME_LIMIT_MS = 10_000
# the whole run (all tests) ends here; the judge stops a little earlier and says TLE itself
RUN_TOTAL_SECONDS = 60
JUDGE_TOTAL_MS = 55_000

# memory of a run container (MiB): the task's limit within [64, 512], 256 without one
DEFAULT_MEMORY_MB = 256
MIN_MEMORY_MB = 64
MAX_MEMORY_MB = 512
# compiling is outside the task's limit: g++ with bits/stdc++.h needs far more than 61 MiB
COMPILE_MEMORY_MB = 512
COMPILE_SECONDS = 15  # inside the judge; the runner allows a little more


def time_limit_ms(requested: int | None) -> int:
    if not requested:
        return DEFAULT_TIME_LIMIT_MS
    return max(MIN_TIME_LIMIT_MS, min(requested, MAX_TIME_LIMIT_MS))


def memory_limit_mb(requested: int | None) -> int:
    if not requested:
        return DEFAULT_MEMORY_MB
    return max(MIN_MEMORY_MB, min(requested, MAX_MEMORY_MB))


@dataclass(frozen=True)
class ContainerOptions:
    create: dict  # APIClient.create_container(**create, host_config=...)
    host: dict  # APIClient.create_host_config(**host)


def container_options(
    *, image: str, command: list[str], name: str, mem_bytes: int, cpus: float, nofile: int = 64
) -> ContainerOptions:
    host = {
        "network_mode": "none",
        "read_only": True,
        "init": True,
        # /work is where the program lives and runs (exec); /tmp is scratch (no exec)
        "tmpfs": {
            "/tmp": "rw,noexec,nosuid,nodev,size=16m,mode=1777",  # noqa: S108
            "/work": f"rw,exec,nosuid,nodev,size=64m,uid={SANDBOX_UID},gid={SANDBOX_UID},mode=0700",
        },
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "pids_limit": 64,
        "mem_limit": mem_bytes,
        "memswap_limit": mem_bytes,  # no swap: over the limit means killed, not slow
        "nano_cpus": int(cpus * 1e9),
        "ulimits": [
            Ulimit(name="nofile", soft=nofile, hard=nofile),
            Ulimit(name="fsize", soft=16 * MIB, hard=16 * MIB),
            Ulimit(name="core", soft=0, hard=0),
        ],
        # code and tests go in through stdin and the verdict comes out through stdout: no logs kept
        "log_config": LogConfig(type=LogConfig.types.NONE),
        "shm_size": "8m",
    }
    create = {
        "image": image,
        "command": command,
        "name": name,
        "user": f"{SANDBOX_UID}:{SANDBOX_UID}",
        "working_dir": "/work",
        "labels": dict(LABEL),
        "detach": False,  # with stdin_open this makes StdinOnce true: stdin closes after the client's EOF
        "stdin_open": True,
        "tty": False,
        "environment": {},
    }
    return ContainerOptions(create=create, host=host)
