import asyncio
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from infrastructure.redis.client import get_redis
from services.battle_engine import manager
from services.code_executor import execute_and_test_code
from services.django_callbacks import (
    fetch_task_from_django,
    notify_django_battle_finished,
    notify_django_battle_started,
    notify_django_user_joined,
    notify_django_user_left,
)

router = APIRouter()


async def watch_battle_timeout(battle_id: int, deadline: float):
    sleep_time = deadline - time.time()

    if sleep_time > 0:
        await asyncio.sleep(sleep_time)

    redis = await get_redis()
    is_finished = await redis.get(f"battle:{battle_id}:finished")

    if not is_finished:
        await redis.set(f"battle:{battle_id}:finished", "1", ex=3600)

        await manager.broadcast(
            battle_id,
            {
                "event": "battle_finished",
                "data": {"winner_id": None, "reason": "time_up"},
            },
        )
        await notify_django_battle_finished(battle_id, None)


@router.websocket("/ws/battle/{battle_id}/{user_id}")
async def battle_websocket(
    websocket: WebSocket, battle_id: int, user_id: int, username: str
):
    await manager.connect(websocket, battle_id, user_id)
    redis = await get_redis()

    asyncio.create_task(notify_django_user_joined(battle_id, user_id))

    await manager.broadcast(
        battle_id,
        {"event": "user_joined", "data": {"user_id": user_id, "username": username}},
    )

    deadline = await redis.get(f"battle:{battle_id}:deadline")
    if deadline:
        await websocket.send_json(
            {"event": "battle_started", "data": {"deadline": float(deadline)}}
        )

    is_battle_finished_normally = False

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "start_battle_request":
                current_deadline = await redis.get(f"battle:{battle_id}:deadline")
                current_count = len(manager.active_battles.get(battle_id, {}))

                if not current_deadline and current_count >= 1:
                    start_data = await notify_django_battle_started(battle_id, user_id)

                    if start_data and "deadline" in start_data:
                        new_deadline = float(start_data["deadline"])

                        await redis.set(
                            f"battle:{battle_id}:deadline", new_deadline, ex=86400
                        )

                        await manager.broadcast(
                            battle_id,
                            {
                                "event": "battle_started",
                                "data": {"deadline": new_deadline},
                            },
                        )

                        asyncio.create_task(
                            watch_battle_timeout(battle_id, new_deadline)
                        )

            elif action == "submit_code":
                is_finished = await redis.get(f"battle:{battle_id}:finished")
                if is_finished:
                    await websocket.send_json(
                        {"event": "error", "data": {"message": "Battle is over"}}
                    )
                    continue

                language = data.get("language")
                code = data.get("code", None)
                task_id = data.get("task_id")

                await manager.broadcast(
                    battle_id,
                    {
                        "event": "opponent_running_code",
                        "data": {"user_id": user_id, "username": username},
                    },
                )

                task_data = await fetch_task_from_django(task_id)

                if not task_data:
                    await websocket.send_json(
                        {
                            "event": "error",
                            "data": {"message": "Failed to load task data"},
                        }
                    )
                    continue

                result = await execute_and_test_code(task_data, language, code)

                await manager.send_personal(
                    battle_id, user_id, {"event": "execution_result", "data": result}
                )

                if result.get("is_correct"):
                    is_battle_finished_normally = True

                    await redis.set(f"battle:{battle_id}:finished", "1", ex=3600)

                    await manager.broadcast(
                        battle_id,
                        {
                            "event": "battle_finished",
                            "data": {
                                "winner_id": user_id,
                                "winner_username": username,
                                "reason": "solved",
                            },
                        },
                    )

                    await redis.delete(f"battle:{battle_id}:deadline")

                    asyncio.create_task(
                        notify_django_battle_finished(battle_id, user_id)
                    )
                    break

    except WebSocketDisconnect:
        manager.disconnect(battle_id, user_id)

        await manager.broadcast(
            battle_id,
            {"event": "user_left", "data": {"user_id": user_id, "username": username}},
        )

        participants_count = len(manager.active_battles.get(battle_id, {}))
        await manager.broadcast(
            battle_id,
            {
                "event": "lobby_update",
                "data": {"participants_count": participants_count},
            },
        )

        if not is_battle_finished_normally:
            asyncio.create_task(notify_django_user_left(battle_id, user_id))
