# ruff: noqa: S101, S106
"""FastAPI -> sandbox runner, over HTTP (the runner is a fake behind httpx.MockTransport)."""

import json

import httpx
import pytest

from .conftest import CORRECT, next_id
from .fake_django import TASK

pytestmark = pytest.mark.usefixtures("server")


async def submit(server, code=CORRECT, language="python"):
    response = await server.rest(
        "POST", "/api/tasks/1/submit", next_id(), json={"language": language, "code": code}
    )
    assert response.status_code == 200, response.text
    return response.json()


def runner_says(status=200, **answer):
    def respond(_body):
        return httpx.Response(status, json=answer)

    return respond


async def test_request_to_the_runner_has_token_tests_split_and_limits(server):
    result = await submit(server, "print(1)", "cpp")
    assert result["is_correct"] is True

    (body,) = server.runner.requests
    assert server.runner.auth == ["Bearer test-runner-token-0123456789abcdef0123456"]
    assert body["language"] == "cpp" and body["code"] == "print(1)"
    # public tests are shown, only generated ones are hidden; private_tests are never sent
    assert body["tests"]["public"] == [{"input": "1\n", "output": "1"}]
    assert body["tests"]["hidden"] == [{"input": "HIDDEN-IN-777\n", "output": "HIDDEN-OUT-888"}]
    assert body["time_limit_ms"] == 1000 and body["memory_limit_mb"] == 256


async def test_limits_without_values_are_left_to_the_runner(server, monkeypatch):
    monkeypatch.setitem(TASK, "time_limit", None)
    monkeypatch.setitem(TASK, "memory_limit_bytes", 0)
    await submit(server)
    assert server.runner.requests[0]["time_limit_ms"] is None
    assert server.runner.requests[0]["memory_limit_mb"] is None


async def test_fractional_limits_round_up(server, monkeypatch):
    monkeypatch.setitem(TASK, "time_limit", {"seconds": 1, "nanos": 500_000_001})
    monkeypatch.setitem(TASK, "memory_limit_bytes", 64_000_000)  # 61.03 MiB
    await submit(server)
    assert server.runner.requests[0]["time_limit_ms"] == 1501
    assert server.runner.requests[0]["memory_limit_mb"] == 62


async def test_unsupported_language_never_reaches_the_runner(server):
    result = await submit(server, language="brainfuck")
    assert result["verdict"] == "error" and "not supported" in result["details"]
    assert server.runner.requests == []


@pytest.mark.parametrize(
    ("runner_verdict", "verdict", "words"),
    [
        ("TLE", "time_limit", "Time limit exceeded"),
        ("RE", "runtime_error", "Runtime error"),
        ("MLE", "memory_limit", "Memory limit exceeded"),
        ("WA", "wrong_answer", "Incorrect answer"),
    ],
)
async def test_public_failure_shows_input_expected_actual_and_stderr(server, runner_verdict, verdict, words):
    server.runner.override = runner_says(
        verdict=runner_verdict, passed=0, total=3, failed_test={"number": 1, "hidden": False},
        time_ms=1000, memory_mb=None,
        detail={"input": "1\n", "expected": "1", "actual": "7", "stderr": "Traceback boom", "reason": "exit code 1"},
    )
    result = await submit(server)
    assert result["status"] == "failed" and result["is_correct"] is False
    assert result["verdict"] == verdict and result["test_number"] == 1 and result["hidden"] is False
    assert result["message"].startswith(f"{words} on test case #1")
    assert "Input:\n1" in result["details"] and "Expected:\n1" in result["details"]
    assert "Output:\n7" in result["details"] and "Stderr:\nTraceback boom" in result["details"]
    assert result["passed"] == 0 and result["total"] == 3 and result["time_ms"] == 1000


@pytest.mark.parametrize("runner_verdict", ["TLE", "RE", "MLE", "WA"])
async def test_hidden_failure_is_a_number_and_a_verdict_only(server, runner_verdict):
    # a runner that sends too much (it should not): none of it reaches the player
    server.runner.override = runner_says(
        verdict=runner_verdict, passed=1, total=3, failed_test={"number": 2, "hidden": True},
        detail={"input": "SECRET-IN", "expected": "SECRET-OUT", "actual": "SECRET-ACTUAL",
                "stderr": "SECRET-STDERR", "reason": "SECRET-REASON"},
        logs="SECRET-LOGS",
    )
    result = await submit(server)
    assert result["hidden"] is True and result["test_number"] == 2
    assert "hidden test case #2" in result["message"]
    assert "SECRET" not in json.dumps(result)


async def test_compile_error_is_one_result_with_the_compiler_message(server):
    server.runner.override = runner_says(verdict="CE", passed=0, total=3, failed_test=None,
                                         compile_log="main.cpp:1:5: error: expected ';'")
    result = await submit(server, language="cpp")
    assert result["verdict"] == "compile_error" and result["is_correct"] is False
    assert result["message"] == "Compilation error"
    assert result["details"] == "main.cpp:1:5: error: expected ';'"
    assert "test_number" not in result


async def test_a_run_that_ran_out_of_time_without_a_failed_test(server):
    server.runner.override = runner_says(verdict="TLE", passed=0, total=3, failed_test=None)
    result = await submit(server)
    assert result["verdict"] == "time_limit" and result["message"] == "Time limit exceeded"
    assert "test_number" not in result and "details" not in result


async def test_accepted_carries_the_numbers(server):
    server.runner.override = runner_says(verdict="OK", passed=3, total=3, failed_test=None,
                                         time_ms=40, memory_mb=21.5)
    result = await submit(server)
    assert result["verdict"] == "accepted" and result["status"] == "success"
    assert (result["passed"], result["total"], result["time_ms"], result["memory_mb"]) == (3, 3, 40, 21.5)


@pytest.mark.parametrize(
    ("override", "words"),
    [
        (runner_says(503, error="busy"), "busy"),
        (runner_says(503, error="sandbox_unavailable"), "temporarily unavailable"),
        (runner_says(401, error="unauthorized"), "temporarily unavailable"),
        (runner_says(200, verdict="SOMETHING-NEW"), "unreadable"),
    ],
)
async def test_a_runner_that_cannot_judge_gives_a_clean_error_result(server, override, words):
    server.runner.override = override
    result = await submit(server)
    assert result["verdict"] == "error" and result["is_correct"] is False
    assert words in result["details"]
    assert "runner.test" not in json.dumps(result) and "Traceback" not in json.dumps(result)


async def test_runner_down_is_a_clean_error_result(server):
    def refuse(_body):
        raise httpx.ConnectError("connection refused")

    server.runner.override = refuse
    result = await submit(server)
    assert result["verdict"] == "error" and "temporarily unavailable" in result["details"]
    assert "refused" not in json.dumps(result)
