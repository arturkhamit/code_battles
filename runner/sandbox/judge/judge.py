"""In-sandbox judge. Stdlib only; the same file goes into the Python and the C++ sandbox image.

  judge.py run      stdin: a tar stream with job.json, the program and the tests; stdout: ONE JSON line
  judge.py compile  stdin: a tar stream with main.cpp;   stdout: a JSON line, then the binary if ok

Nothing here comes from argv: the runner sends everything through stdin (a tar stream, it ends
by itself, so the judge never waits for an EOF that Docker may not deliver). The tests live in
THIS process's memory and never touch the disk, so the user's program, which runs under the same
uid, cannot read the expected outputs. The judge makes itself non-dumpable (no ptrace, no
/proc/<pid>/mem for the program) and prints the verdict to its own stdout, which the program
cannot reach: a program can at worst kill the judge, and no verdict at all is never "OK".

Every test is a separate process in its own session with its own deadline, stdout and stderr in
separate pipes (both capped), the exit status told apart: signal / non-zero code / clean exit.
"""

import ctypes
import json
import os
import resource
import selectors
import signal
import subprocess
import sys
import tarfile
import time

WORK = os.environ.get("JUDGE_WORK_DIR", "/work")
# Set by the sandbox images only: after each test kill every process of this uid, so a program
# that daemonised itself cannot disturb the next test. Never on a developer machine: kill(-1)
# is "everything I may signal".
KILL_ALL = os.environ.get("JUDGE_KILL_ALL") == "1"

KEEP = 1024  # bytes of actual output / stderr that go back to the runner
OUT_CAP_MIN = 64 * 1024  # a program may print this much whatever the expected output is
OUT_CAP_MAX = 4 * 1024 * 1024
STDERR_CAP = 64 * 1024  # read this much, drain the rest
COMPILE_KEEP = 2048
COMPILE_READ_CAP = 1 << 20
COMPILE_TIMEOUT_S = 15

CHILD_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/tmp",  # noqa: S108 - the sandbox's own tmpfs
    "TMPDIR": "/tmp",  # noqa: S108
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONDONTWRITEBYTECODE": "1",
}

MEMORY_MARKERS = (b"MemoryError", b"std::bad_alloc", b"Cannot allocate memory")
PROGRAM_FILES = {"solution.py": 0o644, "main": 0o755, "main.cpp": 0o644}


# --- comparison ------------------------------------------------------------------------------


def normalize(data: bytes) -> list[str]:
    """Line by line, trailing whitespace of each line ignored, trailing empty lines ignored."""
    lines = [line.rstrip() for line in data.decode("utf-8", errors="replace").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def clip(data: bytes, limit: int = KEEP) -> str:
    text = data[:limit].decode("utf-8", errors="replace")
    return text + "\n...(truncated)" if len(data) > limit else text


def out_cap_for(expected: bytes) -> int:
    return min(max(OUT_CAP_MIN, 2 * len(expected) + 1024), OUT_CAP_MAX)


# --- process plumbing -------------------------------------------------------------------------


def make_undumpable() -> None:
    try:
        ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE = 0
    except Exception:  # noqa: BLE001, S110 - not available outside Linux; a hardening, not a must
        pass


def kill_stragglers(pgid: int | None) -> None:
    """SIGKILL the process group of a test; inside the sandbox image also everything else of this uid."""
    targets = ([-pgid] if pgid else []) + ([-1] if KILL_ALL else [])
    for target in targets:
        try:
            os.kill(target, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _prepare_child(stack_bytes: int) -> None:
    """Runs in the child between fork and exec."""
    try:
        # the judge is non-dumpable and the fork inherits that: /proc/self would be root-owned
        ctypes.CDLL(None).prctl(4, 1, 0, 0, 0)
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("1000")  # if the cgroup runs out of memory, the program dies, never the judge
    except (OSError, AttributeError):
        pass
    for which, value in ((resource.RLIMIT_STACK, stack_bytes), (resource.RLIMIT_CORE, 0)):
        try:
            resource.setrlimit(which, (value, value))
        except (ValueError, OSError):
            pass


def _stdin_file(data: bytes) -> int:
    if hasattr(os, "memfd_create"):
        fd = os.memfd_create("stdin")
    else:  # pragma: no cover - not Linux
        import tempfile

        fd = os.dup(tempfile.TemporaryFile().fileno())  # noqa: SIM115
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]
    os.lseek(fd, 0, os.SEEK_SET)
    return fd


def signal_name(number: int) -> str:
    try:
        return signal.Signals(number).name
    except ValueError:
        return f"signal {number}"


def run_one(argv: list[str], data: bytes, expected: bytes, limit_s: float, stack_bytes: int) -> dict:
    """One test. Returns {verdict, time_ms, memory_kb, actual, stderr, reason}; verdict is one of
    OK, WA, TLE, RE, MLE."""
    cap = out_cap_for(expected)
    judge_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    stdin_fd = _stdin_file(data)
    try:
        proc = subprocess.Popen(
            argv,
            stdin=stdin_fd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=WORK,
            env=CHILD_ENV,
            close_fds=True,
            start_new_session=True,
            preexec_fn=lambda: _prepare_child(stack_bytes),  # noqa: PLW1509
        )
    except OSError as exc:  # no pid left, no memory: the program never started
        return {"verdict": "RE", "time_ms": 0, "memory_kb": 0, "actual": "", "stderr": "",
                "reason": f"could not start the program: {exc.strerror}"}
    finally:
        os.close(stdin_fd)

    out, err = bytearray(), bytearray()
    sel = selectors.DefaultSelector()
    for stream, sink in ((proc.stdout, out), (proc.stderr, err)):
        os.set_blocking(stream.fileno(), False)
        sel.register(stream, selectors.EVENT_READ, sink)

    started = time.monotonic()
    deadline = started + limit_s
    judge_kill = None  # "tle" | "output" when the judge itself ended the program
    status = None
    rusage = None

    def pump(timeout: float) -> None:
        nonlocal judge_kill
        if not sel.get_map():
            time.sleep(min(timeout, 0.002))
            return
        for key, _ in sel.select(timeout):
            try:
                chunk = os.read(key.fd, 65536)
            except BlockingIOError:
                continue
            if not chunk:
                sel.unregister(key.fileobj)
                continue
            sink = key.data
            if sink is out:
                out.extend(chunk)
                if len(out) > cap:
                    judge_kill = "output"
            elif len(err) < STDERR_CAP:
                err.extend(chunk[: STDERR_CAP - len(err)])

    try:
        while True:
            pump(max(0.0, min(0.01, deadline - time.monotonic())))
            done, status, rusage = os.wait4(proc.pid, os.WNOHANG)
            if done:
                break
            if judge_kill is None and time.monotonic() >= deadline:
                judge_kill = "tle"
            if judge_kill:
                kill_stragglers(proc.pid)
                _, status, rusage = os.wait4(proc.pid, 0)
                break
        elapsed = time.monotonic() - started
        for _ in range(16):  # what the program wrote before it ended is still in the pipes
            before = len(out) + len(err)
            pump(0)
            if len(out) + len(err) == before:
                break
        if len(out) > cap:
            judge_kill = judge_kill or "output"
    finally:
        sel.close()
        proc.stdout.close()
        proc.stderr.close()
        kill_stragglers(proc.pid)
        proc.returncode = 0 if status is None else os.waitstatus_to_exitcode(status)

    # ru_maxrss of a forked child starts at the judge's own peak (exec keeps the parent's high-water
    # mark), so a program lighter than the judge reads as the judge: say "unknown" instead of that
    program_rss = int(rusage.ru_maxrss) if rusage else 0
    base = {
        "time_ms": int(elapsed * 1000),
        "memory_kb": program_rss if program_rss > judge_rss else 0,
        "actual": clip(out),
        "stderr": clip(err),
        "reason": None,
    }
    if judge_kill == "tle" or (judge_kill is None and elapsed > limit_s):
        return {**base, "verdict": "TLE"}
    if judge_kill == "output":
        return {**base, "verdict": "WA", "reason": "output limit exceeded"}
    out_of_memory = any(marker in err for marker in MEMORY_MARKERS)
    if os.WIFSIGNALED(status):
        sig = os.WTERMSIG(status)
        if sig == signal.SIGKILL:  # nobody but the kernel's OOM killer is left to do this
            return {**base, "verdict": "MLE", "reason": "killed: out of memory"}
        if out_of_memory:  # std::bad_alloc ends in abort()
            return {**base, "verdict": "MLE", "reason": "out of memory"}
        return {**base, "verdict": "RE", "reason": f"killed by {signal_name(sig)}"}
    code = os.WEXITSTATUS(status)
    if code != 0:
        if out_of_memory:
            return {**base, "verdict": "MLE", "reason": "out of memory"}
        return {**base, "verdict": "RE", "reason": f"exit code {code}"}
    if normalize(out) == normalize(expected):
        return {**base, "verdict": "OK"}
    return {**base, "verdict": "WA"}


# --- modes ------------------------------------------------------------------------------------


def read_archive(stream) -> dict[str, bytes]:
    """The program and job.json go to WORK; tests stay in memory (in/<n>, out/<n>)."""
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = member.name
            data = tar.extractfile(member).read()
            if name in PROGRAM_FILES:
                fd = os.open(os.path.join(WORK, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, PROGRAM_FILES[name])
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
            elif name == "job.json" or (name.split("/", 1)[0] in ("in", "out") and name.split("/", 1)[-1].isdigit()):
                files[name] = data
    return files


def judge_run(files: dict[str, bytes]) -> dict:
    job = json.loads(files["job.json"])
    count = int(job["count"])
    limit_s = int(job["time_limit_ms"]) / 1000
    total_s = int(job["total_budget_ms"]) / 1000
    stack = max(8 << 20, min(int(job["memory_limit_bytes"]), 256 << 20))
    argv = [sys.executable, "-B", os.path.join(WORK, "solution.py")] if job["language"] == "python" else [os.path.join(WORK, "main")]

    started = time.monotonic()
    result = {"verdict": "OK", "passed": 0, "total": count, "failed_index": None,
              "time_ms": 0, "memory_kb": 0, "detail": None}
    for index in range(count):
        remaining = total_s - (time.monotonic() - started)
        if remaining <= 0:
            result.update(verdict="TLE", failed_index=index, detail={"reason": "total time exceeded"})
            break
        test = run_one(argv, files[f"in/{index}"], files[f"out/{index}"], min(limit_s, remaining), stack)
        result["time_ms"] = max(result["time_ms"], test["time_ms"])
        result["memory_kb"] = max(result["memory_kb"], test["memory_kb"])
        if test["verdict"] != "OK":
            if test["verdict"] == "TLE" and remaining < limit_s:
                test["reason"] = "total time exceeded"
            result.update(verdict=test["verdict"], failed_index=index, detail={
                "actual": test["actual"], "stderr": test["stderr"], "reason": test["reason"]})
            break
        result["passed"] += 1
    return result


def judge_compile(files: dict[str, bytes]) -> tuple[dict, bytes]:
    del files  # main.cpp is already in WORK
    cmd = ["g++", "-O2", "-std=gnu++17", "-pipe", "-o", os.path.join(WORK, "main"), os.path.join(WORK, "main.cpp")]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=WORK,
                            env=CHILD_ENV, start_new_session=True)
    try:
        log, _ = proc.communicate(timeout=COMPILE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        kill_stragglers(proc.pid)
        proc.communicate()
        return {"ok": False, "log": f"Compilation timed out after {COMPILE_TIMEOUT_S} s"}, b""
    finally:
        kill_stragglers(proc.pid)
    if proc.returncode != 0:
        text = clip(log[:COMPILE_READ_CAP], COMPILE_KEEP).replace(WORK + "/", "")
        return {"ok": False, "log": text}, b""
    with open(os.path.join(WORK, "main"), "rb") as f:
        binary = f.read()
    return {"ok": True, "size": len(binary)}, binary


def main(argv: list[str]) -> int:
    make_undumpable()
    mode = argv[0] if argv else ""
    out = sys.stdout.buffer
    try:
        files = read_archive(sys.stdin.buffer)
        if mode == "run":
            out.write(json.dumps(judge_run(files)).encode() + b"\n")
        elif mode == "compile":
            header, binary = judge_compile(files)
            out.write(json.dumps(header).encode() + b"\n" + binary)
        else:
            raise SystemExit("usage: judge.py run|compile")
    except Exception as exc:  # noqa: BLE001 - the runner must always get a parsable answer
        out.write(json.dumps({"verdict": "ERROR", "ok": False, "reason": f"judge failed: {type(exc).__name__}"}).encode() + b"\n")
        out.flush()
        print(f"judge failed: {exc!r}", file=sys.stderr)
        return 3
    out.flush()
    kill_stragglers(None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
