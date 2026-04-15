import logging

import httpx
from core.config import settings

logger = logging.getLogger(__name__)


async def notify_django_user_joined(battle_id: int, user_id: int):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/battles/join/{battle_id}/"
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}
            payload = {"user_id": user_id}

            response = await client.patch(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info("Django notified: User %d joined battle %d", user_id, battle_id)
            else:
                logger.error("Error notifying Django (join): %s", response.text)
        except Exception as e:
            logger.exception("HTTP error (join): %s", e)


async def notify_django_user_left(battle_id: int, user_id: int):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/battles/leave/{battle_id}/"
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}
            payload = {"user_id": user_id}

            response = await client.patch(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info("Django notified: User %d left battle %d", user_id, battle_id)
        except Exception as e:
            logger.exception("HTTP error (leave): %s", e)


async def notify_django_battle_started(battle_id: int, user_id: int) -> dict | None:
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/battles/start/{battle_id}/"
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}
            payload = {"user_id": user_id}

            response = await client.patch(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                logger.info("Battle %d started. Deadline: %s", battle_id, data.get("deadline"))
                return data
            else:
                logger.error("Error starting battle in Django: %s", response.text)
                return None
        except Exception as e:
            logger.exception("HTTP error (start): %s", e)
            return None


async def notify_django_battle_finished(battle_id: int, winner_id: int | None):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/battles/finish/{battle_id}/"

            payload = {"winner_id": winner_id}
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}

            response = await client.patch(url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info("Django successfully updated: Battle %d finished", battle_id)
        except Exception as e:
            logger.exception("Error sending finish status to Django: %s", e)


async def notify_django_delete_battle(battle_id: int):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/battles/delete/{battle_id}/"
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}

            response = await client.delete(url, headers=headers)
            if response.status_code == 204:
                logger.info("Django deleted idle battle %d", battle_id)
            else:
                logger.error("Error deleting battle in Django: %s", response.text)
        except Exception as e:
            logger.exception("HTTP error (delete): %s", e)


async def fetch_task_from_django(task_id: int) -> dict | None:
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/tasks/{task_id}/"
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}

            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    "Error fetching task from Django: %d - %s",
                    response.status_code,
                    response.text,
                )
                return None

        except Exception as e:
            logger.exception("FastAPI can't reach Django: %s", e)
            return None
