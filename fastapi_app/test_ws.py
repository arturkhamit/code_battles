import asyncio
import json
import os

import websockets


async def player_1():
    uri = "ws://localhost:8001/ws/battle/99/1"

    async with websockets.connect(uri) as ws:
        print("🟢 Игрок 1 подключился")

        await asyncio.sleep(2)
        print("📤 Игрок 1 отправляет НЕВЕРНЫЙ код...")

        # Добавили task_id внутрь JSON, как ожидает твой код
        await ws.send(
            json.dumps(
                {
                    "action": "submit_code",
                    "language": "python",
                    "code": "print('no')",
                    "task_id": 1,
                }
            )
        )

        try:
            while True:
                msg = await ws.recv()
                print(f"[Игрок 1 получил]: {msg}")
        except websockets.exceptions.ConnectionClosed:
            print("🔴 Игрок 1: Соединение закрыто (Игра окончена)")


async def player_2():
    uri = "ws://localhost:8001/ws/battle/99/2"
    await asyncio.sleep(1)

    if not os.path.exists("solution.py"):
        print("❌ Файл solution.py не найден для Игрока 2!")
        return

    with open("solution.py", "r", encoding="utf-8") as f:
        real_code = f.read()

    async with websockets.connect(uri) as ws:
        print("🟢 Игрок 2 подключился")

        await asyncio.sleep(5)
        print("📤 Игрок 2 отправляет ПРАВИЛЬНЫЙ код...")

        await ws.send(
            json.dumps(
                {
                    "action": "submit_code",
                    "language": "python",
                    "code": real_code,
                    "task_id": 1,
                }
            )
        )

        try:
            while True:
                msg = await ws.recv()
                print(f"[Игрок 2 получил]: {msg}")
        except websockets.exceptions.ConnectionClosed:
            print("🔴 Игрок 2: Соединение закрыто (Игра окончена)")


async def main():
    await asyncio.gather(player_1(), player_2())


if __name__ == "__main__":
    asyncio.run(main())
