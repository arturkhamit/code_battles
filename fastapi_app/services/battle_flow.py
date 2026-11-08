"""Battle state kept in Redis (so it survives a restart of this process): deadline, finished flag,
meta (the task of the battle, from Django), the time-up timers and the idle clean-up.

  battle:{id}:deadline  epoch seconds, set on start (TTL 24 h), removed when the battle ends
  battle:{id}:finished  "1" once the result is decided; SET NX makes "solved" and "time up"
                        race safely, also between workers
  battle:{id}:meta      hash {task_id}: the only source of the task a submission is judged on
  battle:{id}:idle_ttl  expires 5 minutes after the last socket left -> Django deletes the battle
"""

import asyncio
import logging
import re
import time
from contextlib import suppress

from core.tasks import spawn
from infrastructure.redis.client import get_redis, redis_db
from services import django_callbacks as django
from services.battle_engine import manager

logger = logging.getLogger(__name__)

DEADLINE_TTL = 86400
FINISHED_TTL = 3600
META_TTL = 86400
KEYSPACE_CHECK_INTERVAL = 15.0

_DEADLINE_KEY = re.compile(r"^battle:(\d+):deadline$")
_IDLE_KEY = re.compile(r"^battle:(\d+):idle_ttl$")

_timers: dict[int, asyncio.Task] = {}


def remaining_seconds(deadline: float) -> float:
    return max(0.0, round(deadline - time.time(), 1))


def started_event(deadline: float) -> dict:
    return {
        "event": "battle_started",
        "data": {"deadline": deadline, "remaining_seconds": remaining_seconds(deadline)},
    }


# --- meta -----------------------------------------------------------------------------------


async def save_meta(battle_id: int, task_id: int | None) -> None:
    if task_id is None:
        return
    redis = get_redis()
    key = f"battle:{battle_id}:meta"
    await redis.hset(key, "task_id", task_id)
    await redis.expire(key, META_TTL)


async def get_task_id(battle_id: int) -> int | None:
    value = await get_redis().hget(f"battle:{battle_id}:meta", "task_id")
    return int(value) if value is not None else None


# --- start / finish -------------------------------------------------------------------------


async def begin(battle_id: int, deadline: float) -> None:
    await get_redis().set(f"battle:{battle_id}:deadline", deadline, ex=DEADLINE_TTL)
    arm_timer(battle_id, deadline)
    await manager.publish(battle_id, started_event(deadline))


async def finish_battle(
    battle_id: int, winner_id: int | None, winner_username: str | None, reason: str
) -> bool:
    """Decide the battle once. False if somebody (another socket, the timer) already did."""
    redis = get_redis()
    if not await redis.set(f"battle:{battle_id}:finished", "1", nx=True, ex=FINISHED_TTL):
        return False
    await redis.delete(f"battle:{battle_id}:deadline")
    timer = _timers.pop(battle_id, None)
    if timer and timer is not asyncio.current_task():
        timer.cancel()

    # Django first: the outbox keeps the result even if the publish below fails
    spawn(django.finish_reliably(battle_id, winner_id), name=f"finish-{battle_id}")
    await manager.publish(
        battle_id,
        {
            "event": "battle_finished",
            "data": {
                "winner_id": winner_id,
                "winner_username": winner_username,
                "reason": reason,
            },
        },
    )
    logger.info(
        "Battle finished: %s", reason,
        extra={"battle_id": battle_id, "user_id": winner_id},
    )
    return True


# --- time-up timers -------------------------------------------------------------------------


def arm_timer(battle_id: int, deadline: float) -> None:
    timer = _timers.get(battle_id)
    if timer and not timer.done():
        return
    _timers[battle_id] = spawn(_time_up(battle_id, deadline), name=f"timer-{battle_id}")


async def _time_up(battle_id: int, deadline: float) -> None:
    try:
        delay = deadline - time.time()
        if delay > 0:
            await asyncio.sleep(delay)
        await finish_battle(battle_id, None, None, "time_up")
    finally:
        if _timers.get(battle_id) is asyncio.current_task():
            del _timers[battle_id]


async def rearm_timers() -> int:
    """After a restart: put a timer back on every battle that still has a deadline in Redis."""
    redis = get_redis()
    armed = 0
    async for key in redis.scan_iter(match="battle:*:deadline", count=200):
        match = _DEADLINE_KEY.match(key)
        raw = await redis.get(key) if match else None
        if raw is None:
            continue
        battle_id = int(match.group(1))
        if await redis.exists(f"battle:{battle_id}:finished"):
            await redis.delete(key)
            continue
        arm_timer(battle_id, float(raw))
        armed += 1
    logger.info("Re-armed %d battle timers", armed)
    return armed


def cancel_timers() -> None:
    for timer in list(_timers.values()):
        timer.cancel()
    _timers.clear()


# --- idle clean-up (Redis keyspace events) --------------------------------------------------


async def ensure_keyspace_events() -> None:
    """Idle expiry reaches us as a keyevent: Redis must have E (keyevent) and x (expired) on.
    A restarted Redis forgets the setting, so this runs again after every reconnect."""
    redis = get_redis()
    try:
        current = (await redis.config_get("notify-keyspace-events")).get("notify-keyspace-events", "")
        if "E" in current and ("x" in current or "A" in current):
            return
        await redis.config_set("notify-keyspace-events", "".join(sorted(set(current) | {"E", "x"})))
        logger.info("notify-keyspace-events enabled")
    except Exception as exc:
        logger.warning(
            "Could not enable keyspace notifications: %s. "
            "Start Redis with --notify-keyspace-events Ex", exc,
        )


async def idle_listener() -> None:
    """Run under supervise(). Plain `async for pubsub.listen()` would never notice that a
    restarted Redis lost the keyspace setting while redis-py quietly re-subscribed."""
    await ensure_keyspace_events()
    pubsub = get_redis().pubsub()
    last_check = time.monotonic()
    try:
        await pubsub.subscribe(f"__keyevent@{redis_db()}__:expired")
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            if time.monotonic() - last_check > KEYSPACE_CHECK_INTERVAL:
                await ensure_keyspace_events()
                last_check = time.monotonic()
            if message is None:
                continue
            match = _IDLE_KEY.match(message["data"])
            if match:
                await _delete_idle_battle(int(match.group(1)))
    finally:
        with suppress(Exception):
            await pubsub.aclose()


async def _delete_idle_battle(battle_id: int) -> None:
    logger.info("Idle timer expired, deleting battle", extra={"battle_id": battle_id})
    try:
        await django.delete_battle(battle_id)
    except django.DjangoError as exc:
        if exc.status != 404:
            # 409: the battle is running or over, its deadline timer must stay; 5xx: nothing
            # was deleted. Either way keep the keys.
            logger.warning("Idle battle not deleted: %s", exc, extra={"battle_id": battle_id})
            return
    redis = get_redis()
    for suffix in ("deadline", "finished", "meta"):
        await redis.delete(f"battle:{battle_id}:{suffix}")
