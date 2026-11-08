"""WS /ws/battle/{id}?token=JWT[&role=player|spectator][&invite=CODE]

Close codes (the socket is accepted first so the client can read them):
  1008 bad token (handshake rejected) | 4001 replaced by a newer socket of the same user
  4400 bad role/invite or Django 400  | 4403 private battle without a valid invite
  4404 no such battle or user         | 4409 battle finished, full or already started (role=player)
  4429 too many connections           | 1011 Django unreachable / 5xx / server error
Client messages are validated by schemas/ws.py; server events are listed in the report to the
frontend (see also frontend/src/types/ws.ts).
"""

import logging
import time

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from redis.exceptions import RedisError

from core.auth import get_current_user_ws
from infrastructure.redis.client import get_redis
from schemas.ws import MAX_FRAME_BYTES, RoleAssigned, SendChat, StartBattle, SubmitCode, client_message
from services import battle_flow, limits
from services import django_callbacks as django
from services.battle_engine import Conn, manager
from services.code_executor import execute_and_test_code

logger = logging.getLogger(__name__)
router = APIRouter()

CLOSE_BY_STATUS = {400: 4400, 403: 4403, 404: 4404, 409: 4409}
WS_RATE_LIMITED = 4429
ROLES = ("player", "spectator")
MAX_INVITE_CHARS = 64

ERROR_BY_STATUS = {400: "bad_request", 403: "forbidden", 404: "not_found", 409: "conflict"}


def error_event(code: str, message: str, **extra) -> dict:
    return {"event": "error", "data": {"code": code, "message": message, **extra}}


def _reason(text: str) -> str:
    return text.encode()[:120].decode(errors="ignore")  # a close reason is at most 123 bytes


def _django_error_event(exc: django.DjangoError) -> dict:
    if exc.unavailable:
        return error_event("service_unavailable", "Game service is temporarily unavailable")
    code = ERROR_BY_STATUS.get(exc.status, "service_error")
    return error_event(code, exc.detail or "Request refused")


def _validation_error_event(exc: ValidationError) -> dict:
    first = exc.errors(include_input=False, include_url=False)[0]
    field = str(first["loc"][-1]) if first["loc"] else ""
    if first["type"] == "json_invalid":
        return error_event("invalid_json", "Message is not valid JSON")
    if first["type"] == "string_too_long" and field == "code":
        return error_event("code_too_large", "Code is too long (64 KiB at most)")
    if first["type"] == "string_too_long" and field == "message":
        return error_event("message_too_long", "Chat message is too long (1000 characters at most)")
    where = f" ({field})" if field else ""
    return error_event("invalid_message", f"Invalid message{where}: {first['msg']}")


@router.websocket("/ws/battle/{battle_id}")
async def battle_websocket(
    websocket: WebSocket,
    battle_id: int,
    role: str | None = Query(None),
    invite: str | None = Query(None),
    current_user: dict = Depends(get_current_user_ws),
):
    user_id: int = current_user["user_id"]
    await websocket.accept()

    try:
        await limits.check_ws_connect(user_id)
    except limits.RateLimited as exc:
        await websocket.send_json(error_event("rate_limited", exc.message, retry_after=exc.retry_after))
        await websocket.close(code=WS_RATE_LIMITED, reason="rate_limited")
        return
    except RedisError:
        logger.error("Redis is unavailable: closing the socket", extra={"user_id": user_id})
        await websocket.close(code=1011, reason="service unavailable")
        return

    if role not in (None, *ROLES) or (invite is not None and len(invite) > MAX_INVITE_CHARS):
        await websocket.close(code=4400, reason="invalid role or invite")
        return

    joined = await _join(websocket, battle_id, current_user, role, invite)
    if joined is None:
        return
    conn, assigned = joined

    try:
        await _announce(conn, assigned)
        await _serve(conn)
    except WebSocketDisconnect:
        pass
    finally:
        await _leave(conn)


async def _join(websocket, battle_id, user, role, invite) -> tuple[Conn, RoleAssigned] | None:
    """Ask Django for a place and register the socket. Closes the socket and returns None on
    any refusal: a failed join never leaves a half-joined user behind (fail-closed)."""
    user_id = user["user_id"]
    with manager.joining(battle_id, user_id):
        try:
            joined = await django.join(battle_id, user_id, role, invite)
        except django.DjangoError as exc:
            code = CLOSE_BY_STATUS.get(exc.status, 1011)
            reason = "service unavailable" if code == 1011 else exc.detail
            logger.warning("Join refused: %s", exc, extra={"battle_id": battle_id, "user_id": user_id})
            await websocket.close(code=code, reason=_reason(reason))
            return None

        conn = Conn(
            ws=websocket,
            battle_id=battle_id,
            user_id=user_id,
            username=user["username"],
            role=joined["role"],
            task_id=joined.get("task_id"),
        )
        try:
            assigned = RoleAssigned.model_validate(
                {**joined, "battle_id": battle_id, "is_creator": joined["creator_id"] == user_id}
            )
            await battle_flow.save_meta(battle_id, conn.task_id)
            await manager.register(conn)
        except Exception:
            logger.exception("Could not register the socket", extra={"battle_id": battle_id, "user_id": user_id})
            conn = None
    if conn is None:  # Django has the user in the battle: give the place back
        await _leave(Conn(websocket, battle_id, user_id, user["username"], "player", None))
        await websocket.close(code=1011, reason="server error")
        return None
    logger.info("Joined as %s", conn.role, extra={"battle_id": battle_id, "user_id": user_id})
    return conn, assigned


async def _announce(conn: Conn, assigned: RoleAssigned) -> None:
    await conn.ws.send_json({"event": "role_assigned", "data": assigned.model_dump()})
    await manager.publish(
        conn.battle_id,
        {
            "event": "user_joined",
            "data": {"user_id": conn.user_id, "username": conn.username, "role": conn.role},
        },
    )
    deadline = await get_redis().get(f"battle:{conn.battle_id}:deadline")
    if deadline:  # a reconnect into a running battle
        await conn.ws.send_json(battle_flow.started_event(float(deadline)))


async def _serve(conn: Conn) -> None:
    ws = conn.ws
    while True:
        message = await ws.receive()
        if message["type"] == "websocket.disconnect":
            return
        raw = message.get("text")
        if raw is None:
            await ws.send_json(error_event("invalid_message", "Binary frames are not supported"))
            continue
        if len(raw) > MAX_FRAME_BYTES or len(raw.encode()) > MAX_FRAME_BYTES:
            await ws.send_json(error_event("message_too_large", "Message is too large (128 KiB at most)"))
            continue

        try:
            msg = client_message.validate_json(raw)
        except ValidationError as exc:
            await ws.send_json(_validation_error_event(exc))
            continue

        try:
            if isinstance(msg, StartBattle):
                await _on_start(conn)
            elif isinstance(msg, SendChat):
                await _on_chat(conn, msg)
            elif isinstance(msg, SubmitCode):
                await _on_submit(conn, msg)
        except Exception:
            logger.exception(
                "Message handler failed", extra={"battle_id": conn.battle_id, "user_id": conn.user_id}
            )
            await ws.send_json(error_event("internal_error", "Server error, try again"))


async def _on_start(conn: Conn) -> None:
    if conn.role != "player":
        await conn.ws.send_json(error_event("spectator_forbidden", "Spectators cannot start the battle"))
        return
    redis = get_redis()
    if await redis.exists(f"battle:{conn.battle_id}:finished"):
        await conn.ws.send_json(error_event("battle_over", "Battle is over"))
        return
    if await redis.exists(f"battle:{conn.battle_id}:deadline"):
        await conn.ws.send_json(error_event("conflict", "Battle has already started"))
        return

    try:
        data = await django.start_battle(conn.battle_id, conn.user_id)
    except django.DjangoError as exc:
        await conn.ws.send_json(_django_error_event(exc))
        return
    deadline = data.get("deadline")
    if not isinstance(deadline, (int, float)):
        await conn.ws.send_json(error_event("service_error", "Server returned no deadline"))
        return
    await battle_flow.begin(conn.battle_id, float(deadline))


async def _on_chat(conn: Conn, msg: SendChat) -> None:
    text = msg.message.strip()
    if text:
        await manager.publish(
            conn.battle_id,
            {
                "event": "chat_message",
                "data": {"user_id": conn.user_id, "username": conn.username, "message": text},
            },
        )


async def _on_submit(conn: Conn, msg: SubmitCode) -> None:
    ws = conn.ws
    if conn.role != "player":
        await ws.send_json(error_event("spectator_forbidden", "Spectators cannot submit code"))
        return
    redis = get_redis()
    if await redis.exists(f"battle:{conn.battle_id}:finished"):
        await ws.send_json(error_event("battle_over", "Battle is over"))
        return
    if not await redis.exists(f"battle:{conn.battle_id}:deadline"):
        await ws.send_json(error_event("battle_not_active", "Battle has not started"))
        return

    # The task comes from Django's join answer, never from the client's message
    task_id = await battle_flow.get_task_id(conn.battle_id) or conn.task_id
    if task_id is None:
        await ws.send_json(error_event("task_unavailable", "Battle has no task"))
        return

    started = time.monotonic()
    try:
        async with limits.run_slot(conn.user_id):
            await manager.publish(
                conn.battle_id,
                {
                    "event": "opponent_running_code",
                    "data": {"user_id": conn.user_id, "username": conn.username},
                },
            )
            task_data = await django.fetch_task(task_id)
            result = await execute_and_test_code(task_data, msg.language, msg.code)
    except limits.RateLimited as exc:
        await ws.send_json(error_event("rate_limited", exc.message, retry_after=exc.retry_after))
        return
    except django.DjangoError as exc:
        logger.warning("Task not loaded: %s", exc, extra={"battle_id": conn.battle_id, "user_id": conn.user_id})
        await ws.send_json(error_event("task_unavailable", "Failed to load task data"))
        return

    logger.info(
        "Submission judged",
        extra={
            "battle_id": conn.battle_id,
            "user_id": conn.user_id,
            "verdict": result.get("verdict"),
            "ms": round((time.monotonic() - started) * 1000),
        },
    )
    await manager.publish_personal(
        conn.battle_id, conn.user_id, {"event": "execution_result", "data": result}
    )
    if result.get("is_correct"):
        await battle_flow.finish_battle(conn.battle_id, conn.user_id, conn.username, "solved")


async def _leave(conn: Conn) -> None:
    """Runs on every exit: disconnect, error, cancellation, the winner too."""
    manager.unregister(conn)
    # Replaced by a newer socket, or that socket is just joining: the user is still in the battle
    if conn.replaced or manager.user_present(conn.battle_id, conn.user_id):
        return

    extra = {"battle_id": conn.battle_id, "user_id": conn.user_id}
    try:
        await manager.publish(
            conn.battle_id,
            {"event": "user_left", "data": {"user_id": conn.user_id, "username": conn.username}},
        )
        if not manager.has_local_connections(conn.battle_id):
            await manager.set_idle_timer(conn.battle_id)
    except Exception:
        logger.exception("Could not announce the departure", extra=extra)
    try:
        await django.leave(conn.battle_id, conn.user_id)
    except django.DjangoError as exc:
        logger.warning("Leave not delivered: %s", exc, extra=extra)
