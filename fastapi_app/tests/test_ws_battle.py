# ruff: noqa: S101, S106
import asyncio
import json
import time

import pytest
from websockets.exceptions import InvalidStatus

from .conftest import CORRECT, FAIL_HIDDEN, WRONG, next_id

pytestmark = pytest.mark.usefixtures("server")


async def two_players(server, **battle_kwargs):
    a, b = next_id(), next_id()
    battle = server.battle(a, **battle_kwargs)
    ws_a = await server.connect(battle, a)
    await ws_a.wait_for("role_assigned")
    ws_b = await server.connect(battle, b)
    await ws_b.wait_for("role_assigned")
    return battle, a, b, ws_a, ws_b


async def test_role_assigned_carries_the_lobby_state_and_who_the_creator_is(server):
    """A fresh socket misses the lobby_update Django sent before it registered."""
    a, b = next_id(), next_id()
    battle = server.battle(a, task=7)
    ws_a = await server.connect(battle, a)
    first = await ws_a.wait_for("role_assigned")
    ws_b = await server.connect(battle, b)
    second = await ws_b.wait_for("role_assigned")

    common = {"battle_id": battle, "task_id": 7, "type": "1v1", "battle_status": "pending",
              "max_participants": 2, "creator_id": a, "role": "player",
              "creator_username": f"user{a}", "duration": 1.0}
    assert first["data"] == {**common, "players_count": 1, "is_creator": True}
    assert second["data"] == {**common, "players_count": 2, "is_creator": False}


# --- fail-closed join -------------------------------------------------------------------------


async def test_bad_token_is_rejected_at_the_handshake(server):
    with pytest.raises(InvalidStatus) as err:
        await server.connect(1, 1, token="garbage")
    assert err.value.response.status_code == 403


async def test_unknown_battle_closes_4404(server):
    ws = await server.connect(987654321, next_id())
    code, _ = await ws.closed()
    assert code == 4404
    assert "role_assigned" not in ws.events()


async def test_full_1v1_third_player_closes_4409_and_is_not_added(server):
    battle, a, b, ws_a, ws_b = await two_players(server)
    c = next_id()
    ws_c = await server.connect(battle, c, role="player")
    code, reason = await ws_c.closed()
    assert code == 4409 and "full" in reason.lower()
    assert c not in server.fake.battles[battle]["parts"]
    assert "role_assigned" not in ws_c.events()


async def test_third_user_without_role_is_a_spectator_who_cannot_submit(server):
    battle, a, b, ws_a, ws_b = await two_players(server)
    ws_c = await server.connect(battle, next_id())
    assert (await ws_c.wait_for("role_assigned"))["data"]["role"] == "spectator"
    await ws_a.send(action="start_battle_request")
    await ws_c.wait_for("battle_started")

    await ws_c.send(action="submit_code", language="python", code=CORRECT)
    error = await ws_c.wait_for("error")
    assert error["data"]["code"] == "spectator_forbidden"
    await ws_c.send(action="start_battle_request")
    assert (await ws_c.wait_for("error"))["data"]["code"] == "spectator_forbidden"
    assert server.fake.battles[battle]["status"] == "active"  # nobody won


async def test_private_battle_needs_the_invite(server):
    creator = next_id()
    battle = server.battle(creator, invite="SECRET1")
    ws = await server.connect(battle, next_id())
    assert (await ws.closed())[0] == 4403

    ws = await server.connect(battle, next_id(), invite="SECRET1")
    await ws.wait_for("role_assigned")
    assert server.fake.joins[-1]["invite_code"] == "SECRET1"


async def test_finished_battle_closes_4409(server):
    battle = server.battle(next_id(), status="finished")
    assert (await (await server.connect(battle, next_id())).closed())[0] == 4409


async def test_bad_role_closes_4400(server):
    battle = server.battle(next_id())
    assert (await (await server.connect(battle, next_id(), role="admin")).closed())[0] == 4400


async def test_django_down_closes_1011_and_nobody_is_in_the_battle(server):
    battle = server.battle(next_id())
    server.fake.down = True
    try:
        ws = await server.connect(battle, next_id())
        code, _ = await ws.closed(timeout=10)
    finally:
        server.fake.down = False
    assert code == 1011
    assert "role_assigned" not in ws.events()


async def test_joining_a_started_battle_without_role_makes_a_spectator(server):
    battle = server.battle(next_id(), status="active")
    ws = await server.connect(battle, next_id())
    assert (await ws.wait_for("role_assigned"))["data"]["role"] == "spectator"


# --- integrity: the task comes from the server -------------------------------------------------


async def test_client_task_id_is_ignored(server):
    battle, a, b, ws_a, ws_b = await two_players(server, task=1)
    await ws_a.send(action="start_battle_request")
    await ws_a.wait_for("battle_started")
    server.fake.task_requests.clear()

    await ws_b.send(action="submit_code", language="python", code=CORRECT, task_id=2)
    await ws_b.wait_for("battle_finished")
    assert server.fake.task_requests == [1]


async def test_task_id_is_cached_in_redis_meta(server, redis_sync):
    battle, *_ = await two_players(server, task=1)
    assert redis_sync.hget(f"battle:{battle}:meta", "task_id") == "1"


# --- a whole battle ---------------------------------------------------------------------------


async def test_full_battle_wrong_then_right(server):
    battle, a, b, ws_a, ws_b = await two_players(server, duration_seconds=60)
    assert (await ws_a.wait_for("user_joined"))["data"]["user_id"] == a  # int, not "14"

    await ws_b.send(action="start_battle_request")  # b is no creator
    err = await ws_b.wait_for("error")
    assert err["data"]["code"] == "forbidden"

    await ws_a.send(action="start_battle_request")
    started = await ws_b.wait_for("battle_started")
    assert 55 <= started["data"]["remaining_seconds"] <= 60
    assert abs(started["data"]["deadline"] - time.time() - 60) < 5

    await ws_a.send(action="submit_code", language="python", code=WRONG)
    result = await ws_a.wait_for("execution_result")
    assert result["data"]["is_correct"] is False
    assert "opponent_running_code" in await _events_of(ws_b, "opponent_running_code")
    assert "execution_result" not in ws_b.events()  # the result goes to its author only

    await ws_b.send(action="submit_code", language="python", code=CORRECT)
    done = await ws_a.wait_for("battle_finished")
    assert done["data"] == {"winner_id": b, "winner_username": f"user{b}", "reason": "solved"}
    assert isinstance(done["data"]["winner_id"], int)
    await _eventually(lambda: (battle, b) in server.fake.finishes)

    await ws_a.send(action="submit_code", language="python", code=CORRECT)
    assert (await ws_a.wait_for("error"))["data"]["code"] == "battle_over"


async def test_time_up_is_a_draw_with_null_winner_username(server):
    battle, a, b, ws_a, ws_b = await two_players(server, duration_seconds=1)
    await ws_a.send(action="start_battle_request")
    done = await ws_b.wait_for("battle_finished", timeout=5)
    assert done["data"] == {"winner_id": None, "winner_username": None, "reason": "time_up"}
    await _eventually(lambda: (battle, None) in server.fake.finishes)


async def test_reconnect_into_running_battle_keeps_role_and_gets_remaining_seconds(server):
    battle, a, b, ws_a, ws_b = await two_players(server, duration_seconds=60)
    await ws_a.send(action="start_battle_request")
    await ws_b.wait_for("battle_started")
    await ws_b.close()
    await _eventually(lambda: (battle, b) in server.fake.left)

    ws_b2 = await server.connect(battle, b)
    assert (await ws_b2.wait_for("role_assigned"))["data"]["role"] == "player"
    started = await ws_b2.wait_for("battle_started")
    assert 0 < started["data"]["remaining_seconds"] <= 60


async def test_hidden_tests_do_not_leak_over_ws(server):
    battle, a, b, ws_a, ws_b = await two_players(server)
    await ws_a.send(action="start_battle_request")
    await ws_a.wait_for("battle_started")
    await ws_b.send(action="submit_code", language="python", code=FAIL_HIDDEN)
    result = (await ws_b.wait_for("execution_result"))["data"]
    assert result["hidden"] is True and result["test_number"] == 2
    assert result["verdict"] == "wrong_answer"
    assert "#2" in result["message"]
    blob = json.dumps(result)
    for secret in ("HIDDEN-IN-777", "HIDDEN-OUT-888", "WRONG-OUT-999"):
        assert secret not in blob


# --- robustness -------------------------------------------------------------------------------


async def test_invalid_input_gives_error_events_and_the_socket_lives(server):
    battle, a, b, ws_a, ws_b = await two_players(server)

    await ws_a.send_raw("{not json")
    assert (await ws_a.wait_for("error"))["data"]["code"] == "invalid_json"
    await ws_a.send_raw("[1, 2]")
    assert (await ws_a.wait_for("error"))["data"]["code"] == "invalid_message"
    await ws_a.send(action="dance")
    assert (await ws_a.wait_for("error"))["data"]["code"] == "invalid_message"
    await ws_a.send(action="submit_code", language="python", code="x" * (64 * 1024 + 1))
    assert (await ws_a.wait_for("error"))["data"]["code"] == "code_too_large"
    await ws_a.send(action="send_chat", message="y" * 1001)
    assert (await ws_a.wait_for("error"))["data"]["code"] == "message_too_long"
    await ws_a.send_raw(" " * (128 * 1024 + 1))
    assert (await ws_a.wait_for("error"))["data"]["code"] == "message_too_large"

    await ws_a.send(action="send_chat", message="still here")
    chat = await ws_b.wait_for("chat_message")
    assert chat["data"]["message"] == "still here"


async def test_second_tab_replaces_the_first_and_no_leave_is_sent(server):
    battle = server.battle(next_id())
    a = next_id()
    tab1 = await server.connect(battle, a)
    await tab1.wait_for("role_assigned")
    tab2 = await server.connect(battle, a)
    await tab2.wait_for("role_assigned")

    code, reason = await tab1.closed()
    assert (code, reason) == (4001, "replaced")
    await asyncio.sleep(0.5)
    assert (battle, a) not in server.fake.left  # the user is still in the battle
    assert server.fake.battles[battle]["parts"].keys() == {a}

    await tab2.send(action="send_chat", message="hi")
    assert (await tab2.wait_for("chat_message"))["data"]["message"] == "hi"
    await tab2.close()
    await _eventually(lambda: (battle, a) in server.fake.left)
    assert server.fake.left.count((battle, a)) == 1


async def test_leave_is_sent_when_the_client_vanishes(server):
    battle = server.battle(next_id())
    a = next_id()
    ws = await server.connect(battle, a)
    await ws.wait_for("role_assigned")
    ws.conn.transport.abort()  # no close frame at all
    await _eventually(lambda: (battle, a) in server.fake.left)


async def test_leave_is_sent_for_the_winner_too(server):
    battle, a, b, ws_a, ws_b = await two_players(server)
    await ws_a.send(action="start_battle_request")
    await ws_a.wait_for("battle_started")
    await ws_b.send(action="submit_code", language="python", code=CORRECT)
    await ws_b.wait_for("battle_finished")
    await ws_b.close()
    await _eventually(lambda: (battle, b) in server.fake.left)
    assert "user_left" in await _events_of(ws_a, "user_left")


async def test_handler_exception_does_not_kill_the_socket_and_leave_still_happens(server, monkeypatch):
    battle, a, b, ws_a, ws_b = await two_players(server)

    async def boom(*_):
        raise RuntimeError("boom")

    monkeypatch.setattr("services.battle_flow.begin", boom)
    await ws_a.send(action="start_battle_request")
    assert (await ws_a.wait_for("error"))["data"]["code"] == "internal_error"
    await ws_a.close()
    await _eventually(lambda: (battle, a) in server.fake.left)


# --- helpers ----------------------------------------------------------------------------------


async def _events_of(ws, name, timeout=5):
    await ws.wait_for(name, timeout)
    return ws.events()


async def _eventually(check, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition not reached in time")
