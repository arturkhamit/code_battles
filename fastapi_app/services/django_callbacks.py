import httpx
from core.config import settings


async def notify_django_user_joined(battle_id: int, user_id: int):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/battles/join/{battle_id}/"
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}
            payload = {"user_id": user_id}

            response = await client.patch(url, json=payload, headers=headers)
            if response.status_code == 200:
                print(f"Django notified: User {user_id} joined battle {battle_id}")
            else:
                print(f"Error notifying Django (join): {response.text}")
        except Exception as e:
            print(f"HTTP error (join): {e}")


async def notify_django_user_left(battle_id: int, user_id: int):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/battles/leave/{battle_id}/"
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}
            payload = {"user_id": user_id}

            response = await client.patch(url, json=payload, headers=headers)
            if response.status_code == 200:
                print(f"Django notified: User {user_id} left battle {battle_id}")
        except Exception as e:
            print(f"HTTP error (leave): {e}")


async def notify_django_battle_started(battle_id: int, user_id: int) -> dict | None:
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/battles/start/{battle_id}/"
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}
            payload = {"user_id": user_id}

            response = await client.patch(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                print(f"Battle {battle_id} started! Deadline: {data.get('deadline')}")
                return data
            else:
                print(f"Error starting battle in Django: {response.text}")
                return None
        except Exception as e:
            print(f"HTTP error (start): {e}")
            return None


async def notify_django_battle_finished(battle_id: int, winner_id: int):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/battles/finish/{battle_id}/"

            payload = {"winner_id": winner_id}
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}

            response = await client.patch(url, json=payload, headers=headers)
            response.raise_for_status()
            print(f"Django successfully updated: Battle {battle_id} finished")
        except Exception as e:
            print(f"Error sending status to Django: {e}")


async def fetch_task_from_django(task_id: int) -> dict | None:
    async with httpx.AsyncClient() as client:
        try:
            url = f"{settings.DJANGO_API_URL}/tasks/{task_id}/"
            headers = {"Authorization": f"Bearer {settings.SECRET_KEY}"}

            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                print(
                    f"Error while getting task from Django: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            print(f"FastAPI can't reach Django: {e}")
            return None
