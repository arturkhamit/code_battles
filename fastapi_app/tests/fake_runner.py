"""A stand-in for the sandbox runner (runner/), plugged in as the httpx transport of
services.runner_client, so the real client and the real result mapping run. The code text picks
the behaviour; the answers have the shape the real runner sends."""

import asyncio
import json

import httpx

CORRECT, WRONG, FAIL_HIDDEN, SLOW = "CORRECT", "WRONG", "FAIL_HIDDEN", "SLOW"


class FakeRunner:
    def __init__(self):
        self.reset()

    def reset(self):
        self.requests: list[dict] = []  # JSON bodies of POST /run
        self.auth: list[str | None] = []  # their Authorization headers
        self.override = None  # callable(body) -> httpx.Response, or None for the default behaviour

    async def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        self.auth.append(request.headers.get("authorization"))
        if self.override is not None:
            return self.override(body)

        code = body["code"]
        if code == SLOW:
            await asyncio.sleep(1.5)
        public, hidden = body["tests"]["public"], body["tests"]["hidden"]
        total = len(public) + len(hidden)
        answer = {"verdict": "OK", "passed": total, "total": total, "failed_test": None,
                  "time_ms": 12, "memory_mb": None}
        if code == WRONG:
            answer.update(
                verdict="WA", passed=0, failed_test={"number": 1, "hidden": False},
                detail={"input": public[0]["input"], "expected": public[0]["output"],
                        "actual": "WRONG-OUT-999", "stderr": "", "reason": None},
            )
        elif code == FAIL_HIDDEN:
            # what a real runner sends: a number and a verdict. The detail is here on purpose, as a
            # runner that misbehaves: the API must not pass it on.
            answer.update(
                verdict="WA", passed=len(public), failed_test={"number": len(public) + 1, "hidden": True},
                detail={"input": hidden[0]["input"], "expected": hidden[0]["output"],
                        "actual": "WRONG-OUT-999", "stderr": "", "reason": None},
            )
        return httpx.Response(200, json=answer)
