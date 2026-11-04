"""The judge's answer -> the runner's response.

The only place that decides what the caller may see. A failed HIDDEN test is a number and a
verdict: no input, no expected output, no program output, no stderr, no reason text.
"""

from app.schemas import RunRequest

KEEP = 1024  # characters of input / expected / actual / stderr shown for a public test
VERDICTS = ("OK", "WA", "TLE", "RE", "MLE", "CE")


def clip(text: str, limit: int = KEEP) -> str:
    return text if len(text) <= limit else text[:limit] + "\n...(truncated)"


def build_response(answer: dict, request: RunRequest) -> dict:
    public, hidden = request.tests.public, request.tests.hidden
    verdict = answer.get("verdict")
    if verdict not in VERDICTS:
        verdict = "RE"  # a verdict we do not know is not a pass

    memory_kb = answer.get("memory_kb") or 0
    response = {
        "verdict": verdict,
        "passed": int(answer.get("passed", 0)),
        "total": len(public) + len(hidden),
        "failed_test": None,
        "time_ms": answer.get("time_ms"),
        "memory_mb": round(memory_kb / 1024, 1) if memory_kb else None,
    }
    if verdict == "CE":
        response["compile_log"] = clip(str(answer.get("compile_log", "")), 2048)
        response["passed"] = 0
        return response
    if verdict == "OK":
        response["passed"] = response["total"]
        return response

    index = answer.get("failed_index")
    if index is None or not 0 <= index < response["total"]:
        return response  # the run ended without telling which test (clock or memory of the whole run)

    is_hidden = index >= len(public)
    response["failed_test"] = {"number": index + 1, "hidden": is_hidden}
    if not is_hidden:
        case = public[index]
        detail = answer.get("detail") or {}
        response["detail"] = {
            "input": clip(case.input),
            "expected": clip(case.output),
            "actual": clip(str(detail.get("actual", ""))),
            "stderr": clip(str(detail.get("stderr", ""))),
            "reason": detail.get("reason"),
        }
    return response
