"""Rate limits and the run semaphore. All state lives in Redis, so every worker sees the same
numbers and a restart of the process does not reset them.

  submit cooldown      SUBMIT_COOLDOWN_SECONDS per user
  runs per user        1 at a time
  runs per server      MAX_CONCURRENT_RUNS (sorted set of slots with an expiry: a crashed
                       process frees its slot after RUN_SLOT_TTL instead of holding it forever)
  WS connects          WS_CONNECTS_PER_MINUTE per user (fixed window)
"""

import math
import time
import uuid
from contextlib import asynccontextmanager

from core.config import settings
from infrastructure.redis.client import get_redis

# shortcut: a fixed TTL instead of a heartbeat; a run longer than this loses its slot early.
# The runner ends a submission within ~100 s (queue 20 + compile 15 + tests 60); raise this together with that.
RUN_SLOT_TTL = 300

_SLOTS_KEY = "limit:runs:slots"

# drop expired slots, refuse if the server is full, otherwise take a slot (atomic)
_TAKE_SLOT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4])
return 1
"""


class RateLimited(Exception):
    def __init__(self, scope: str, retry_after: int, message: str):
        super().__init__(message)
        self.scope = scope  # cooldown | user_runs | server_runs | ws_connect
        self.retry_after = max(1, retry_after)
        self.message = message


async def check_ws_connect(user_id: int) -> None:
    redis = get_redis()
    key = f"limit:ws:{user_id}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, 60, nx=True)
        pipe.ttl(key)
        count, _, ttl = await pipe.execute()
    if count > settings.WS_CONNECTS_PER_MINUTE:
        raise RateLimited(
            "ws_connect", ttl if ttl > 0 else 60,
            f"Too many connections: at most {settings.WS_CONNECTS_PER_MINUTE} per minute",
        )


@asynccontextmanager
async def run_slot(user_id: int):
    """Hold the cooldown, the per-user and the server-wide slot around one sandbox run."""
    redis = get_redis()

    cooldown = settings.SUBMIT_COOLDOWN_SECONDS
    if cooldown and not await redis.set(f"limit:submit:{user_id}", "1", nx=True, ex=cooldown):
        pttl = await redis.pttl(f"limit:submit:{user_id}")
        raise RateLimited(
            "cooldown", math.ceil(max(pttl, 0) / 1000),
            f"Wait {cooldown} seconds between submissions",
        )

    token = uuid.uuid4().hex
    user_key = f"limit:run:{user_id}"
    if not await redis.set(user_key, token, nx=True, ex=RUN_SLOT_TTL):
        raise RateLimited("user_runs", 2, "You already have a submission running")

    try:
        now = time.time()
        taken = await redis.eval(
            _TAKE_SLOT, 1, _SLOTS_KEY, now, settings.MAX_CONCURRENT_RUNS, now + RUN_SLOT_TTL, token
        )
        if not taken:
            raise RateLimited("server_runs", 2, "The server is busy running other submissions")
    except BaseException:
        await _release_user(user_key, token)
        raise

    try:
        yield
    finally:
        await redis.zrem(_SLOTS_KEY, token)
        await _release_user(user_key, token)


async def _release_user(user_key: str, token: str) -> None:
    redis = get_redis()
    if await redis.get(user_key) == token:
        await redis.delete(user_key)
