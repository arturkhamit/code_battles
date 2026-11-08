"""Client for Django's internal API (`DJANGO_INTERNAL_URL`, Bearer INTERNAL_API_TOKEN).

Every function returns Django's JSON on 200 and raises DjangoError otherwise:
  DjangoError.status 400/403/404/409 - Django said no (the caller maps it);
  DjangoError.unavailable            - network error, timeout or 5xx (status None or >= 500).
One httpx client lives for the whole app (start/close from the lifespan). Idempotent calls
(join, leave, finish, tasks) are retried with backoff; start is not: a retry of a request
that did reach Django would answer 409 and hide the success.
"""

import asyncio
import json
import logging

import httpx

from core.config import settings
from infrastructure.redis.client import get_redis

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 2.0
READ_TIMEOUT = 5.0
TASKS_READ_TIMEOUT = 15.0  # task detail carries every test of the task
RETRY_BASE_DELAY = 0.2
LOG_BODY_LIMIT = 500  # Django used to answer with 100+ KB HTML pages

OUTBOX_KEY = "outbox:finish"
OUTBOX_MAX_DELAY = 30.0

_client: httpx.AsyncClient | None = None
_transport: httpx.AsyncBaseTransport | None = None  # tests plug a fake Django in here


class DjangoError(Exception):
    def __init__(self, status: int | None, detail: str = ""):
        super().__init__(f"Django {status}: {detail}" if status else f"Django unreachable: {detail}")
        self.status = status
        self.detail = detail

    @property
    def unavailable(self) -> bool:
        return self.status is None or self.status >= 500


async def start() -> None:
    global _client
    _client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {settings.INTERNAL_API_TOKEN}"},
        timeout=httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT),
        transport=_transport,
    )


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _detail(response: httpx.Response) -> str:
    """Human readable reason from a DRF error body; falls back to the (cut) raw text."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:LOG_BODY_LIMIT]
    if isinstance(body, dict) and isinstance(body.get("detail"), str):
        return body["detail"][:LOG_BODY_LIMIT]
    return json.dumps(body)[:LOG_BODY_LIMIT]


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
    read_timeout: float = READ_TIMEOUT,
    retries: int = 0,
) -> dict:
    if _client is None:
        raise RuntimeError("Django client is not started (app lifespan has not run)")
    url = f"{settings.DJANGO_INTERNAL_URL.rstrip('/')}{path}"
    timeout = httpx.Timeout(read_timeout, connect=CONNECT_TIMEOUT)

    for attempt in range(retries + 1):
        error: DjangoError
        try:
            response = await _client.request(
                method, url, json=json_body, params=params, timeout=timeout
            )
        except httpx.HTTPError as exc:
            error = DjangoError(None, f"{type(exc).__name__}: {exc}")
        else:
            if response.status_code < 300:
                if not response.content:
                    return {}
                try:
                    return response.json()
                except ValueError:
                    error = DjangoError(502, "Django answered with a non-JSON body")
            else:
                error = DjangoError(response.status_code, _detail(response))
            logger.warning(
                "Django %s %s -> %s %s",
                method, path, response.status_code, response.text[:LOG_BODY_LIMIT],
            )

        if not error.unavailable or attempt == retries:
            raise error
        delay = RETRY_BASE_DELAY * 2**attempt
        logger.warning("Django %s %s: %s; retry %d in %.1fs", method, path, error.detail, attempt + 1, delay)
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def join(
    battle_id: int, user_id: int, role: str | None = None, invite_code: str | None = None
) -> dict:
    body: dict = {"user_id": user_id}
    if role:
        body["role"] = role
    if invite_code:
        body["invite_code"] = invite_code
    return await _request("PATCH", f"/battles/join/{battle_id}/", json_body=body, retries=2)


async def leave(battle_id: int, user_id: int) -> dict:
    return await _request(
        "PATCH", f"/battles/leave/{battle_id}/", json_body={"user_id": user_id}, retries=2
    )


async def start_battle(battle_id: int, user_id: int) -> dict:
    return await _request("PATCH", f"/battles/start/{battle_id}/", json_body={"user_id": user_id})


async def finish(battle_id: int, winner_id: int | None, retries: int = 2) -> dict:
    return await _request(
        "PATCH", f"/battles/finish/{battle_id}/", json_body={"winner_id": winner_id}, retries=retries
    )


async def delete_battle(battle_id: int) -> dict:
    return await _request("DELETE", f"/battles/delete/{battle_id}/")


async def fetch_task(task_id: int) -> dict:
    return await _request(
        "GET", f"/tasks/{task_id}/", read_timeout=TASKS_READ_TIMEOUT, retries=2
    )


async def fetch_tasks(limit: int, offset: int, filters: dict | None = None) -> dict:
    """The catalog page; `filters` are the already validated ?search/difficulty/... params."""
    return await _request(
        "GET", "/tasks/", params={**(filters or {}), "limit": limit, "offset": offset},
        read_timeout=TASKS_READ_TIMEOUT, retries=2,
    )


async def fetch_task_facets() -> dict:
    return await _request("GET", "/tasks/facets/", read_timeout=TASKS_READ_TIMEOUT, retries=2)


async def check_ready() -> None:
    """Django readiness (incl. Postgres) for /ready: no retries, short timeouts. Raises on anything but 200."""
    if _client is None:
        raise RuntimeError("Django client is not started")
    response = await _client.get(settings.DJANGO_READY_URL, timeout=httpx.Timeout(2.0))
    response.raise_for_status()


# --- finish outbox: a battle result must not be lost with Django down ----------------------


def _result_is_final(exc: DjangoError) -> bool:
    # 400 winner is no player, 404 battle gone, 409 closed with another result: asking again
    # changes nothing. Anything else (network, 5xx, 401/403 from a wrong token) is retried.
    return exc.status in (400, 404, 409)


async def finish_reliably(battle_id: int, winner_id: int | None) -> None:
    """Send the result; if Django cannot take it now, park it in Redis for outbox_worker."""
    try:
        await finish(battle_id, winner_id)
        logger.info("Django updated: battle finished", extra={"battle_id": battle_id})
    except DjangoError as exc:
        if _result_is_final(exc):
            logger.error("Django rejected the result of battle %s: %s", battle_id, exc,
                         extra={"battle_id": battle_id})
            return
        await get_redis().rpush(
            OUTBOX_KEY, json.dumps({"battle_id": battle_id, "winner_id": winner_id})
        )
        logger.error("Result of battle %s queued in the outbox: %s", battle_id, exc,
                     extra={"battle_id": battle_id})


async def outbox_worker() -> None:
    """Deliver queued results until Django answers 200, 400, 404 or 409. Run under supervise()."""
    delay = 1.0
    while True:
        redis = get_redis()
        failed = False
        for raw in await redis.lrange(OUTBOX_KEY, 0, -1):
            try:
                entry = json.loads(raw)
                await finish(int(entry["battle_id"]), entry["winner_id"], retries=0)
            except DjangoError as exc:
                if not _result_is_final(exc):
                    failed = True
                    continue
                logger.error("Outbox: result dropped: %s", exc)
            except (ValueError, KeyError, TypeError):
                logger.error("Outbox: unreadable entry dropped: %.200s", raw)
            else:
                logger.info("Outbox: result delivered", extra={"battle_id": entry["battle_id"]})
            await redis.lrem(OUTBOX_KEY, 1, raw)
        delay = min(delay * 2, OUTBOX_MAX_DELAY) if failed else 1.0
        await asyncio.sleep(delay)
