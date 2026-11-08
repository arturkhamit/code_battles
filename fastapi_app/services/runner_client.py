"""Client for the sandbox runner (runner/): POST /run with Bearer RUNNER_TOKEN.

This process never starts containers and never sees a Docker socket: code, tests and limits go
over HTTP, a verdict comes back. One httpx client for the whole app (start/close from the lifespan).
"""

import logging

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 3.0
LOG_BODY_LIMIT = 300

_client: httpx.AsyncClient | None = None
_transport: httpx.AsyncBaseTransport | None = None  # tests plug a fake runner in here


class RunnerError(Exception):
    """The runner could not judge. `busy` = it is full (try again soon), otherwise it is unavailable."""

    def __init__(self, detail: str, *, busy: bool = False):
        super().__init__(detail)
        self.busy = busy


async def start() -> None:
    global _client
    _client = httpx.AsyncClient(
        base_url=settings.RUNNER_URL.rstrip("/"),
        headers={"Authorization": f"Bearer {settings.RUNNER_TOKEN}"},
        timeout=httpx.Timeout(settings.RUNNER_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT),
        transport=_transport,
    )


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def run(
    language: str,
    code: str,
    public: list[dict],
    hidden: list[dict],
    time_limit_ms: int | None,
    memory_limit_mb: int | None,
) -> dict:
    """Tests are {"input": str, "output": str}. Returns the runner's verdict JSON."""
    if _client is None:
        raise RuntimeError("Runner client is not started (app lifespan has not run)")
    body = {
        "language": language,
        "code": code,
        "tests": {"public": public, "hidden": hidden},
        "time_limit_ms": time_limit_ms,
        "memory_limit_mb": memory_limit_mb,
    }
    try:
        response = await _client.post("/run", json=body)
    except httpx.HTTPError as exc:
        raise RunnerError(f"{type(exc).__name__}: {exc}") from exc

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as exc:
            raise RunnerError("runner answered with a non-JSON body") from exc
    logger.error("Runner answered %s: %s", response.status_code, response.text[:LOG_BODY_LIMIT])
    # 503 with "busy" is a full runner; anything else (401, 413, 422, 5xx) is a fault on our side
    raise RunnerError(f"HTTP {response.status_code}", busy=response.status_code == 503 and "busy" in response.text)
