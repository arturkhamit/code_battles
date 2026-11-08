"""Judging a submission: the tests of the task go to the sandbox runner, its verdict becomes the
`execution_result` the frontend shows.

Public tests are shown in full when they fail. Everything else (private and generated tests) is
hidden: the player gets the number of the failed test and the verdict, never its input, expected
output, the program's output or stderr. The runner already leaves those out; this module does not
copy them even if a runner ever sent them.

execution_result: status ("success" | "failed" | "error"), is_correct, verdict, message,
  details?, test_number?, hidden?, and (from the runner) passed?, total?, time_ms?, memory_mb?.
verdict: accepted | wrong_answer | time_limit | runtime_error | memory_limit | compile_error | error
"""

import logging
import math

from services import runner_client

logger = logging.getLogger(__name__)

LANGUAGES = ("python", "cpp")
# private_tests are not judged: in the dataset they sometimes belong to another task (task 761 holds answers of hexagonal numbers)
HIDDEN_GROUPS = ("generated_tests",)
MIB = 1 << 20

VERDICTS = {  # runner verdict -> (verdict, what happened)
    "WA": ("wrong_answer", "Incorrect answer"),
    "TLE": ("time_limit", "Time limit exceeded"),
    "RE": ("runtime_error", "Runtime error"),
    "MLE": ("memory_limit", "Memory limit exceeded"),
}
HIDDEN_NOTE = "This test is hidden: its input and expected output are not shown."


def _error(details: str) -> dict:
    return {
        "status": "error",
        "is_correct": False,
        "verdict": "error",
        "message": "Execution Error",
        "details": details,
    }


def _tests(task_data: dict, groups: tuple[str, ...]) -> list[dict]:
    tests = []
    for group in groups:
        data = task_data.get(group) or {}
        for inp, out in zip(data.get("input", []), data.get("output", []), strict=False):
            tests.append({"input": inp, "output": out})
    return tests


def _limits(task_data: dict) -> tuple[int | None, int | None]:
    """(time per test in ms, memory in MiB); None = the task has none, the runner picks a default."""
    time_limit = task_data.get("time_limit")
    time_ms = None
    if isinstance(time_limit, dict):
        seconds = (time_limit.get("seconds") or 0) + (time_limit.get("nanos") or 0) / 1e9
        time_ms = math.ceil(seconds * 1000) or None
    memory = task_data.get("memory_limit_bytes")
    return time_ms, (math.ceil(memory / MIB) if memory else None)


async def execute_and_test_code(task_data: dict, language: str, user_code: str) -> dict:
    if language not in LANGUAGES:
        return _error(f"Language {language} is not supported")
    public = _tests(task_data, ("public_tests",))
    hidden = _tests(task_data, HIDDEN_GROUPS)
    if not public and not hidden:
        return {
            "status": "error",
            "is_correct": False,
            "verdict": "error",
            "message": "Task doesn't have test cases",
        }

    time_ms, memory_mb = _limits(task_data)
    try:
        answer = await runner_client.run(language, user_code, public, hidden, time_ms, memory_mb)
    except runner_client.RunnerError as exc:
        logger.error("Runner could not judge: %s", exc)
        if exc.busy:
            return _error("The code runner is busy, try again in a few seconds")
        return _error("The code runner is temporarily unavailable, try again in a minute")
    return to_execution_result(answer)


def to_execution_result(answer: dict) -> dict:
    verdict = answer.get("verdict")
    stats = {k: answer[k] for k in ("passed", "total", "time_ms", "memory_mb") if answer.get(k) is not None}

    if verdict == "OK":
        return {
            "status": "success",
            "is_correct": True,
            "verdict": "accepted",
            "message": "All test cases are successfully completed",
            **stats,
        }
    if verdict == "CE":
        return {
            "status": "failed",
            "is_correct": False,
            "verdict": "compile_error",
            "message": "Compilation error",
            "details": str(answer.get("compile_log") or "The program did not compile"),
            **stats,
        }
    if verdict not in VERDICTS:
        logger.error("Runner sent an unknown verdict: %r", verdict)
        return _error("The code runner gave an unreadable answer")

    name, what = VERDICTS[verdict]
    result = {"status": "failed", "is_correct": False, "verdict": name, **stats}
    failed = answer.get("failed_test")
    if not failed:  # the whole run ran out of time or memory, no single test to blame
        return {**result, "message": what}

    number, hidden = failed["number"], bool(failed["hidden"])
    result["test_number"], result["hidden"] = number, hidden
    if hidden:
        # a number and a verdict, nothing else: whatever else the runner sent is dropped here
        return {**result, "message": f"{what} on hidden test case #{number}", "details": HIDDEN_NOTE}

    detail = answer.get("detail") or {}
    reason = detail.get("reason")
    parts = [
        f"Input:\n{detail.get('input', '')}",
        f"Expected:\n{detail.get('expected', '')}",
        f"Output:\n{detail.get('actual') or '[No output]'}",
    ]
    if detail.get("stderr"):
        parts.append(f"Stderr:\n{detail['stderr']}")
    return {
        **result,
        "message": f"{what} on test case #{number}" + (f" ({reason})" if reason else ""),
        "details": "\n\n".join(parts),
    }
