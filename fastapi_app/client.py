import asyncio
import json
import os
import sys

import websockets


async def listen_to_server(ws):
    """Фоновая задача: постоянно слушает сервер и выводит сообщения"""
    try:
        while True:
            msg = await ws.recv()
            # Красиво форматируем JSON для читаемости
            data = json.loads(msg)
            print(f"\n📩 [СЕРВЕР]: {json.dumps(data, indent=2, ensure_ascii=False)}")
            print(">>> ", end="", flush=True)  # Возвращаем приглашение ко вводу
    except websockets.exceptions.ConnectionClosed:
        print("\n🔴 [СЕРВЕР]: Соединение закрыто (Битва завершена).")
        os._exit(0)  # Жестко завершаем скрипт


async def main():
    # Получаем ID юзера из аргументов командной строки
    if len(sys.argv) < 2:
        print("❌ Ошибка: Укажи ID юзера при запуске!")
        print("👉 Пример: python interactive_client.py 1")
        return

    user_id = sys.argv[1]
    battle_id = 99
    uri = f"ws://localhost:8001/ws/battle/{battle_id}/{user_id}"

    try:
        async with websockets.connect(uri) as ws:
            print(f"🟢 Подключено к битве {battle_id} как ЮЗЕР {user_id}")
            print("-" * 40)
            print("Доступные команды:")
            print("  [1] - Отправить ПЛОХОЙ код (заведомо неверный)")
            print("  [2] - Отправить ХОРОШИЙ код (из файла solution.py)")
            print("  [q] - Выйти")
            print("-" * 40)

            # Запускаем прослушку сервера в фоне
            asyncio.create_task(listen_to_server(ws))

            # Основной цикл: ждем ввода пользователя
            while True:
                # Используем to_thread, чтобы input() не блокировал прослушку сообщений
                cmd = await asyncio.to_thread(input, ">>> ")

                if cmd == "q":
                    break
                elif cmd == "1":
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
                    print("📤 Отправлен плохой код. Ждем вердикт...")
                elif cmd == "2":
                    if os.path.exists("solution.py"):
                        with open("solution.py", "r", encoding="utf-8") as f:
                            code = f.read()
                        await ws.send(
                            json.dumps(
                                {
                                    "action": "submit_code",
                                    "language": "python",
                                    "code": code,
                                    "task_id": 1,
                                }
                            )
                        )
                        print("📤 Отправлен хороший код. Ждем вердикт...")
                    else:
                        print("❌ Файл solution.py не найден в текущей папке!")
                elif cmd != "":
                    print("⚠️ Неизвестная команда. Введи 1, 2 или q.")

    except ConnectionRefusedError:
        print("❌ Не удалось подключиться. FastAPI запущен?")


if __name__ == "__main__":
    asyncio.run(main())
