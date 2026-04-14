# tests/main.py
import time

import pytest
import asyncio
import os
import sys
import random
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# ====================== PYTHONPATH ======================
root_dir = Path(__file__).parent.parent.resolve()
fastapi_dir = root_dir / "fastapi_app"

sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(fastapi_dir))

os.environ["DJANGO_SECRET_KEY"] = "any-dummy-value-for-tests"

from fastapi_app.main import app
from fastapi_app.infrastructure.redis.client import get_redis

# ====================== ФИКСТУРЫ ======================

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_django_post():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        yield mock_post


@pytest.fixture
def mock_django_patch():
    with patch("httpx.AsyncClient.patch", new_callable=AsyncMock) as mock_patch:
        yield mock_patch


@pytest.fixture
def mock_django_get():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        yield mock_get


@pytest.fixture
def mock_redis():
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()
    redis_mock.delete = AsyncMock()

    # 1. Переопределяем зависимость на уровне FastAPI (самый надежный способ для Depends)
    app.dependency_overrides[get_redis] = lambda: redis_mock

    # 2. Патчим импорт так, чтобы любые прямые вызовы тоже возвращали наш мок
    with patch(
        "infrastructure.redis.client.get_redis",
        return_value=redis_mock
    ):
        yield redis_mock

    # Очищаем кэш зависимостей после завершения теста, чтобы не сломать другие
    app.dependency_overrides.clear()

@pytest.fixture
def mock_django_http():
    """Мок для всех типов HTTP запросов к Django."""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as m_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as m_post, \
         patch("httpx.AsyncClient.patch", new_callable=AsyncMock) as m_patch:
        yield {"get": m_get, "post": m_post, "patch": m_patch}

# ====================== ТЕСТЫ ======================

@pytest.mark.asyncio
async def test_complete_battle_flow(
        client,
        mock_django_patch,
        mock_django_get,
        mock_redis,
):
    """
    Оригинальный тест с фиксированным ID битвы.
    """
    battle_id = 16
    user_id = 1
    username = "arthurkhamit"
    task_id = 1
    deadline = 1700000000.0

    # ========== МОКИ ==========
    patch_response = MagicMock()
    patch_response.status_code = 200
    patch_response.json.return_value = {"deadline": deadline}
    mock_django_patch.return_value = patch_response

    get_response = MagicMock()
    get_response.status_code = 200
    get_response.json.return_value = {
        "id": task_id,
        "public_tests": {"input": ["1 2"], "output": ["3"]},
        "time_limit": 2,
        "memory_limit_bytes": 256 * 1024 * 1024,
    }
    mock_django_get.return_value = get_response

    # Мокаем выполнение кода
    with patch(
            "services.code_executor.execute_and_test_code",
            new_callable=AsyncMock,
    ) as mock_execute:
        mock_execute.return_value = {
            "status": "success",
            "is_correct": True,
            "message": "All test cases are successfully completed",
        }

        # Отключаем redis_listener
        with patch("fastapi_app.main.redis_listener", new_callable=AsyncMock):
            with client.websocket_connect(
                    f"/ws/battle/{battle_id}/{user_id}?username={username}"
            ) as ws:
                # 1. Подключение
                data = ws.receive_json()
                assert data["event"] == "user_joined"

                # 2. Старт боя
                ws.send_json({"action": "start_battle_request"})
                data = ws.receive_json()
                assert data["event"] == "battle_started"
                assert data["data"]["deadline"] == deadline

                # 3. Отправка кода
                ws.send_json({
                    "action": "submit_code",
                    "language": "python",
                    "code": "print(1 + 2)",
                    "task_id": task_id,
                })

                # === РОБАСТНЫЙ ПРИЁМ СООБЩЕНИЙ ===
                received_events = []
                for _ in range(3):  # ожидаем максимум 3 сообщения
                    data = ws.receive_json()
                    event = data["event"]
                    received_events.append(event)

                assert "execution_result" in received_events
                assert "battle_finished" in received_events
                assert data["event"] == "battle_finished"
                assert data["data"]["winner_id"] == user_id

            await asyncio.sleep(0.1)

            # Финальные проверки
            assert mock_execute.call_count == 1
            print("✅ Старый тест успешно пройден!")


@pytest.mark.asyncio
async def test_create_and_complete_new_battle_flow(
        client,
        mock_django_post,
        mock_django_patch,
        mock_django_get,
        mock_redis,
):
    """
    Новый тест. Имитирует создание совершенно новой битвы за счет генерации уникального
    идентификатора и мокирования HTTP POST запроса (если он используется для старта/создания).
    Гарантирует отсутствие конфликтов "уже завершенной" битвы в кэше.
    """
    # Динамически генерируем новый battle_id для каждого прогона
    new_battle_id = random.randint(10000, 99999)
    user_id = 2
    username = "new_challenger"
    task_id = 2
    deadline = 1800000000.0

    # ========== МОКИ ==========
    # Мок ответа на создание битвы (если FastAPI делает запрос к Django для инициализации)
    post_response = MagicMock()
    post_response.status_code = 201
    post_response.json.return_value = {"id": new_battle_id, "status": "waiting"}
    mock_django_post.return_value = post_response

    patch_response = MagicMock()
    patch_response.status_code = 200
    patch_response.json.return_value = {"deadline": deadline}
    mock_django_patch.return_value = patch_response

    # Улучшенный мок GET, чтобы возвращать и инфу по таске, и статус битвы "не окончена", если потребуется
    get_response = MagicMock()
    get_response.status_code = 200
    get_response.json.return_value = {
        "id": task_id,
        "status": "active",  # Явно указываем, что статус активен, если код это проверяет
        "public_tests": {"input": ["5 5"], "output": ["10"]},
        "time_limit": {"seconds" : 2},
        "memory_limit_bytes": 256 * 1024 * 1024,
    }
    mock_django_get.return_value = get_response

    # Сбрасываем моки Redis, чтобы гарантировать пустое состояние перед боем
    mock_redis.get.return_value = None

    # Мокаем выполнение кода
    with patch(
            "services.code_executor.execute_and_test_code",
            new_callable=AsyncMock,
    ) as mock_execute:
        mock_execute.return_value = {
            "status": "success",
            "is_correct": True,
            "message": "All test cases are successfully completed",
        }

        # Отключаем redis_listener
        with patch("fastapi_app.main.redis_listener", new_callable=AsyncMock):
            # --- Шаг 0: Если у тебя есть FastAPI эндпоинт для создания битвы, его можно дернуть тут ---
            # response = client.post("/api/battles/create", json={"user_id": user_id})
            # assert response.status_code in [200, 201]

            # Подключаемся с новым сгенерированным ID
            with client.websocket_connect(
                    f"/ws/battle/{new_battle_id}/{user_id}?username={username}"
            ) as ws:
                # 1. Подключение
                data = ws.receive_json()
                assert data["event"] == "user_joined"

                # 2. Старт боя
                ws.send_json({"action": "start_battle_request"})
                data = ws.receive_json()
                assert data["event"] == "battle_started"
                assert data["data"]["deadline"] == deadline

                # 3. Отправка кода
                ws.send_json({
                    "action": "submit_code",
                    "language": "python",
                    "code": "print(5 + 5)",
                    "task_id": task_id,
                })

                # === РОБАСТНЫЙ ПРИЁМ СООБЩЕНИЙ ===
                received_events = []
                for _ in range(3):
                    data = ws.receive_json()
                    event = data["event"]
                    received_events.append(event)
                    print(f"   [New Battle {new_battle_id}] → Получено: {event}")

                # Проверяем события
                assert "execution_result" in received_events
                assert "battle_finished" in received_events
                assert data["event"] == "battle_finished"
                assert data["data"]["winner_id"] == user_id

            await asyncio.sleep(0.1)

            # Проверяем, что кэш обновлялся
            assert mock_redis.set.call_count > 0

            print(f"✅ Тест с новой битвой (ID: {new_battle_id}) успешно пройден!")


@pytest.mark.asyncio
async def test_full_http_and_ws_flow(client, mock_redis, mock_django_http):
    """
    Тест имитирует полный цикл:
    1. 'Создание' битвы через HTTP (mock Django)
    2. Подключение по WS
    3. Старт и завершение
    """
    battle_id = random.randint(1000, 9999)
    user_id = 42
    username = "test_user"
    task_id = 10
    deadline = time.time() + 300

    # --- 1. Настройка ответов Django (HTTP моки) ---

    # Ответ на fetch_task_from_django
    task_resp = MagicMock()
    task_resp.status_code = 200
    task_resp.json.return_value = {
        "id": task_id,
        "public_tests": {"input": ["2 2"], "output": ["4"]},
        "time_limit": {"seconds": 1},
        "memory_limit_bytes": 1024 * 1024
    }
    mock_django_http["get"].return_value = task_resp

    # Ответ на notify_django_battle_started (start_battle_request)
    start_resp = MagicMock()
    start_resp.status_code = 200
    start_resp.json.return_value = {"status": "started", "deadline": deadline}
    mock_django_http["patch"].return_value = start_resp

    # Ответ на notify_django_user_joined / finished (post)
    post_resp = MagicMock()
    post_resp.status_code = 201
    post_resp.json.return_value = {"status": "ok"}
    mock_django_http["post"].return_value = post_resp

    # --- 2. Мок выполнения кода ---
    with patch("services.code_executor.execute_and_test_code", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"status": "success", "is_correct": True}

        # Отключаем фоновый листенер
        with patch("fastapi_app.main.redis_listener", new_callable=AsyncMock):
            # Соединение
            url = f"/ws/battle/{battle_id}/{user_id}?username={username}"
            with client.websocket_connect(url) as ws:
                # Проверка входа
                data = ws.receive_json()
                assert data["event"] == "user_joined"

                # Старт битвы (Action: HTTP PATCH в Django по логике твоего роутера)
                ws.send_json({"action": "start_battle_request"})
                data = ws.receive_json()
                assert data["event"] == "battle_started"
                assert data["data"]["deadline"] == deadline

                # Отправка решения (Action: HTTP GET таски + запуск)
                ws.send_json({
                    "action": "submit_code",
                    "language": "python",
                    "code": "print(4)",
                    "task_id": task_id
                })

                # Собираем ответы (opponent_running -> execution_result -> battle_finished)
                events = []
                for _ in range(3):
                    msg = ws.receive_json()
                    events.append(msg["event"])

                assert "execution_result" in events
                assert "battle_finished" in events

    # Проверка вызовов моков
    assert mock_django_http["get"].call_count >= 1  # Загрузка таски
    assert mock_django_http["patch"].call_count >= 1  # Старт битвы
    assert mock_redis.set.call_count >= 1  # Сохранение deadline/finished в Redis

    print(f"✅ Тест HTTP+WS для битвы {battle_id} пройден успешно!")


@pytest.mark.asyncio
async def test_complete_battle_flow_legacy(client, mock_redis, mock_django_http):
    """Оригинальный тест, адаптированный под новые фикстуры."""
    battle_id = 16
    user_id = 1

    # Настройка моков (упрощенно)
    mock_django_http["patch"].return_value.json.return_value = {"deadline": 1700000000.0}
    mock_django_http["get"].return_value.json.return_value = {
        "id": 1, "public_tests": {"input": []}, "time_limit": {"seconds": 2}
    }

    with patch("services.code_executor.execute_and_test_code", new_callable=AsyncMock) as m_exec:
        m_exec.return_value = {"is_correct": True}
        with patch("fastapi_app.main.redis_listener", new_callable=AsyncMock):
            with client.websocket_connect(f"/ws/battle/{battle_id}/{user_id}?username=art") as ws:
                ws.receive_json()  # joined
                ws.send_json({"action": "start_battle_request"})
                ws.receive_json()  # started
                ws.send_json({"action": "submit_code", "task_id": 1})

                res = [ws.receive_json()["event"] for _ in range(3)]
                assert "battle_finished" in res

    print("✅ Оригинальный тест пройден!")