"""Removes sandbox containers that outlived any legitimate run (a crashed runner, a killed job).

A run is over in well under a minute and a half (compile 15 s + run 60 s, each container removed
right after), so a labelled container older than MAX_AGE_SECONDS is a leftover.
"""

import asyncio
import logging
import time

import docker
import requests

from app.spec import LABEL

logger = logging.getLogger(__name__)

MAX_AGE_SECONDS = 120
INTERVAL_SECONDS = 60


def reap(client: docker.DockerClient, now: float | None = None) -> int:
    """Remove labelled containers older than MAX_AGE_SECONDS. Returns how many."""
    now = time.time() if now is None else now
    label = "{}={}".format(*next(iter(LABEL.items())))
    removed = 0
    for item in client.api.containers(all=True, filters={"label": [label]}):
        if now - item.get("Created", now) <= MAX_AGE_SECONDS:
            continue
        try:
            client.api.remove_container(item["Id"], force=True)
            removed += 1
            logger.warning("Reaper removed a stale sandbox container", extra={"container": item["Id"][:12]})
        except (docker.errors.DockerException, requests.RequestException) as exc:
            logger.error("Reaper could not remove %s: %s", item["Id"][:12], type(exc).__name__)
    return removed


async def reaper_loop(client: docker.DockerClient) -> None:
    """At start and then every INTERVAL_SECONDS. A failure (Docker restarting) is logged, never fatal."""
    while True:
        try:
            await asyncio.to_thread(reap, client)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Reaper pass failed: %s: %s", type(exc).__name__, exc)
        await asyncio.sleep(INTERVAL_SECONDS)
