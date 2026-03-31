import asyncio
import os

import httpx

FASTAPI_URL = "http://localhost:8001/api"


async def test_real_solution():
    task_id = 1

    if not os.path.exists("solution.py"):
        print("❌ Файл solution.py не найден!")
        return

    with open("solution.py", "r", encoding="utf-8") as f:
        real_code = f.read()

    print(f"✅ Прочитан код из solution.py (строк: {len(real_code.splitlines())})")
    print("🚀 Отправляем код в Docker на проверку по всем тестам...")

    # 3. Формируем Body запроса (payload)
    payload = {"language": "python", "code": real_code}

    async with httpx.AsyncClient() as client:
        # Увеличим таймаут, так как тестов может быть много, и Докеру нужно время
        try:
            submit_resp = await client.post(
                f"{FASTAPI_URL}/tasks/{task_id}/submit", json=payload, timeout=30.0
            )

            # Смотрим вердикт судьи
            result = submit_resp.json()
            print("\n🏆 ВЕРДИКТ СУДЬИ:")

            if result.get("is_correct"):
                print("🟩 ACCEPTED (Все тесты пройдены!)")
                print(f"Сообщение: {result.get('message')}")
            else:
                print("🟥 WRONG ANSWER (или ошибка)")
                print(f"Статус: {result.get('status')}")
                print(f"Сообщение: {result.get('message')}")
                print(f"Детали: \n{result.get('details')}")

        except httpx.ReadTimeout:
            print("⏳ Ошибка: Превышено время ожидания ответа от сервера (Timeout).")


if __name__ == "__main__":
    asyncio.run(test_real_solution())
