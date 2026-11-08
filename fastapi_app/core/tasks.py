import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Coroutine

logger = logging.getLogger(__name__)

# The loop keeps only weak references to tasks: hold strong ones or they can vanish mid-run.
_background: set[asyncio.Task] = set()


def spawn(coro: Coroutine, name: str | None = None) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    _background.add(task)
    task.add_done_callback(_background.discard)
    task.add_done_callback(_log_failure)
    return task


def _log_failure(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.error(
            "Background task %s failed", task.get_name(), exc_info=task.exception()
        )


async def supervise(
    name: str,
    run: Callable[[], Awaitable[None]],
    *,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
) -> None:
    """Run `run()` forever: when it fails or returns, wait (exponential backoff) and start again.

    The delay resets once a run lasted a minute. Only cancellation stops the loop.
    """
    delay = base_delay
    while True:
        started = time.monotonic()
        try:
            await run()
            logger.warning("%s ended unexpectedly, restarting in %.1fs", name, delay)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("%s failed: %s: %s; restarting in %.1fs", name, type(exc).__name__, exc, delay)
        if time.monotonic() - started > 60:
            delay = base_delay
        await asyncio.sleep(delay)
        delay = min(delay * 2, max_delay)
