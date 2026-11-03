# ruff: noqa: S101, S106
"""Battle rules on the internal API that FastAPI calls: join, leave, start, finish, delete,
the list, and the events Django sends. Needs Postgres and Redis (see pytest.ini)."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connections, transaction
from rest_framework.exceptions import APIException

from apps.battles.models import Battle, Participant
from apps.battles.services.join_battle import join_battle
from apps.submissions.models import Submission

pytestmark = pytest.mark.django_db


def join(internal, battle, user, **body):
    return internal("patch", f"/internal/battles/join/{battle.id}/", {"user_id": user.id, **body})


def leave(internal, battle, user):
    return internal("patch", f"/internal/battles/leave/{battle.id}/", {"user_id": user.id})


def start(internal, battle, user):
    return internal("patch", f"/internal/battles/start/{battle.id}/", {"user_id": user.id})


def finish(internal, battle, winner):
    body = {"winner_id": winner.id if winner else None}
    return internal("patch", f"/internal/battles/finish/{battle.id}/", body)


def members(battle):
    """(user_id, role, status) of every participant."""
    return list(battle.participants.order_by("id").values_list("user_id", "role", "status"))


@pytest.fixture
def duel(internal, make_battle, make_user):
    """A pending 1v1 whose two players have joined: (battle, creator, rival)."""
    creator, rival = make_user(), make_user()
    battle = make_battle(creator=creator)
    for player in (creator, rival):
        assert join(internal, battle, player).status_code == 200
    return battle, creator, rival


@pytest.fixture
def running_duel(internal, duel):
    battle, creator, rival = duel
    assert start(internal, battle, creator).status_code == 200
    battle.refresh_from_db()
    return battle, creator, rival


# --- join -------------------------------------------------------------------


def test_join_answers_with_the_role_and_the_state_of_the_battle(internal, make_battle, make_user):
    battle, user = make_battle(), make_user()

    response = join(internal, battle, user)

    assert response.status_code == 200
    assert response.json() == {
        "id": Participant.objects.get(user=user).pk,
        "role": "player",
        "status": "waiting",
        "battle_status": "pending",
        "type": "1v1",
        "max_participants": 2,
        "players_count": 1,
        "task_id": battle.task,
        "creator_id": battle.creator_id,
        "creator_username": battle.creator.username,
        "duration": battle.duration,
    }


def test_join_is_idempotent_and_a_player_stays_a_player(internal, duel):
    """A page refresh or a second tab joins again; the battle is full by then."""
    battle, creator, rival = duel
    before = members(battle)

    for _ in range(3):
        response = join(internal, battle, creator)
        assert response.status_code == 200
        assert response.json()["role"] == "player"  # not demoted to a spectator by the full lobby
        assert response.json()["players_count"] == 2

    assert members(battle) == before


def test_without_a_role_a_player_gets_the_free_place_and_a_spectator_the_rest(
    internal, duel, make_user
):
    battle, _, _ = duel
    third = make_user()

    response = join(internal, battle, third)  # the 1v1 is full

    assert response.status_code == 200
    assert (response.json()["role"], response.json()["players_count"]) == ("spectator", 2)
    assert Battle.objects.get(pk=battle.pk).status == "pending"


def test_role_player_in_a_full_battle_is_409(internal, duel, make_user):
    battle, _, _ = duel
    third = make_user()

    response = join(internal, battle, third, role="player")

    assert response.status_code == 409
    assert response.json() == {"detail": "Battle is full."}
    assert not battle.participants.filter(user=third).exists()


def test_players_cannot_join_a_running_battle_but_spectators_can(
    internal, running_duel, make_user
):
    battle, _, _ = running_duel
    watcher, wannabe, explicit = make_user(), make_user(), make_user()

    assert join(internal, battle, wannabe, role="player").status_code == 409
    for user, body in ((watcher, {}), (explicit, {"role": "spectator"})):
        response = join(internal, battle, user, **body)
        assert response.status_code == 200
        assert response.json()["role"] == "spectator"
        assert response.json()["battle_status"] == "active"
        assert response.json()["status"] == "playing"
    assert not battle.participants.filter(user=wannabe).exists()


def test_spectators_do_not_take_places(internal, make_battle, make_user):
    battle = make_battle()
    for _ in range(3):
        assert join(internal, battle, make_user(), role="spectator").status_code == 200

    first, second = make_user(), make_user()
    assert join(internal, battle, first).json()["role"] == "player"
    response = join(internal, battle, second, role="player")

    assert response.status_code == 200  # the two places were free
    assert response.json()["players_count"] == 2
    assert battle.participants.filter(role="spectator").count() == 3


def test_nobody_joins_a_finished_battle(internal, running_duel, make_user):
    battle, creator, rival = running_duel
    assert finish(internal, battle, creator).status_code == 200
    newcomer = make_user()

    for user, body in (
        (newcomer, {}),
        (newcomer, {"role": "player"}),
        (newcomer, {"role": "spectator"}),
        (rival, {}),  # even a member of the finished battle
    ):
        response = join(internal, battle, user, **body)
        assert response.status_code == 409, body
        assert response.json() == {"detail": "Battle is finished."}
    assert not battle.participants.filter(user=newcomer).exists()


def test_join_of_a_private_battle_needs_the_invite_code(internal, make_battle, make_user):
    battle, outsider = make_battle(is_private=True), make_user()

    for body in (
        {},
        {"invite_code": "wrong1"},
        {"invite_code": ""},
        {"invite_code": None},
        {"invite_code": battle.invite_code.swapcase() + "x"},
        {"role": "spectator"},  # a code is needed just to watch, too
    ):
        assert join(internal, battle, outsider, **body).status_code == 403, body
    assert not battle.participants.exists()

    response = join(internal, battle, outsider, invite_code=battle.invite_code)
    assert response.status_code == 200
    assert response.json()["role"] == "player"
    # a member comes back without the code, and the creator never needs it
    assert join(internal, battle, outsider).status_code == 200
    assert join(internal, battle, battle.creator).status_code == 200
    assert battle.participants.count() == 2


def test_a_public_battle_does_not_look_at_the_invite_code(internal, make_battle, make_user):
    battle = make_battle()
    response = join(internal, battle, make_user(), invite_code="whatever")
    assert response.status_code == 200


def test_join_of_an_unknown_battle_or_user_is_404_without_none_in_the_message(
    internal, make_battle, make_user
):
    battle, user = make_battle(), make_user()

    unknown_battle = internal("patch", "/internal/battles/join/99999999/", {"user_id": user.id})
    unknown_user = internal("patch", f"/internal/battles/join/{battle.id}/", {"user_id": 99999999})

    assert unknown_battle.status_code == 404
    assert unknown_battle.json() == {"detail": "Battle not found"}
    assert unknown_user.status_code == 404
    assert unknown_user.json() == {"detail": "User not found"}
    assert not battle.participants.exists()


def test_ids_beyond_the_integer_range_are_client_errors_not_500(internal, make_battle, make_user):
    huge = 10**30
    battle, user = make_battle(), make_user()
    join(internal, battle, user)

    assert internal("patch", f"/internal/battles/join/{huge}/", {"user_id": user.id}).status_code == 404
    assert internal("patch", f"/internal/battles/join/{battle.id}/", {"user_id": huge}).status_code == 404
    assert internal("patch", f"/internal/battles/leave/{battle.id}/", {"user_id": huge}).status_code == 400
    assert internal("patch", f"/internal/battles/start/{battle.id}/", {"user_id": huge}).status_code == 403
    assert internal("patch", f"/internal/battles/finish/{battle.id}/", {"winner_id": huge}).status_code == 400


@pytest.mark.parametrize(
    "body",
    [{}, {"user_id": None}, {"user_id": "x"}, {"user_id": 1, "role": "admin"}, {"user_id": 1, "role": 7}],
)
def test_join_rejects_a_malformed_body_with_400(internal, make_battle, body):
    response = internal("patch", f"/internal/battles/join/{make_battle().id}/", body)
    assert response.status_code == 400


@pytest.mark.parametrize("action", ["join", "leave", "start", "finish"])
def test_a_body_that_is_not_a_json_object_is_400_not_500(api, settings, make_battle, action):
    auth = {"HTTP_AUTHORIZATION": f"Bearer {settings.INTERNAL_API_TOKEN}"}
    url = f"/internal/battles/{action}/{make_battle().id}/"

    for raw in ("{not json", "[1, 2]", "null", '"text"', "7"):
        response = api.patch(url, raw, content_type="application/json", **auth)
        assert response.status_code == 400, raw


def test_join_accepts_nulls_and_a_user_id_as_text(internal, make_battle, make_user):
    """FastAPI sends what it has: the id from the JWT is a string, absent options are null."""
    battle, user = make_battle(), make_user()
    body = {"user_id": str(user.id), "role": None, "invite_code": None}

    response = internal("patch", f"/internal/battles/join/{battle.id}/", body)

    assert response.status_code == 200
    assert response.json()["role"] == "player"


# --- leave ------------------------------------------------------------------


def test_leave_in_a_pending_battle_deletes_the_row_and_frees_the_place(
    internal, duel, make_user
):
    battle, creator, rival = duel
    third = make_user()
    assert join(internal, battle, third, role="player").status_code == 409

    response = leave(internal, battle, rival)

    assert response.status_code == 200
    assert response.json() == {"battle_status": "pending", "players_count": 1}
    assert members(battle) == [(creator.id, "player", "waiting")]
    assert join(internal, battle, third, role="player").status_code == 200


def test_leave_in_a_running_battle_keeps_the_row_and_a_rejoin_gets_the_role_back(
    internal, running_duel
):
    battle, creator, rival = running_duel

    response = leave(internal, battle, creator)

    assert response.status_code == 200
    assert response.json() == {"battle_status": "active", "players_count": 2}
    assert members(battle) == [(creator.id, "player", "disconnected"), (rival.id, "player", "playing")]

    rejoin = join(internal, battle, creator)
    assert rejoin.status_code == 200
    assert (rejoin.json()["role"], rejoin.json()["status"]) == ("player", "playing")
    assert len(members(battle)) == 2


def test_leave_after_the_finish_changes_nothing(internal, running_duel):
    battle, creator, rival = running_duel
    assert finish(internal, battle, creator).status_code == 200
    before = members(battle)

    response = leave(internal, battle, rival)

    assert response.status_code == 200
    assert members(battle) == before == [(creator.id, "player", "finished"), (rival.id, "player", "finished")]


def test_leave_of_a_stranger_is_400_and_of_an_unknown_battle_404(internal, duel, make_user):
    battle, _, _ = duel
    stranger = make_user()

    assert leave(internal, battle, stranger).status_code == 400
    assert internal("patch", "/internal/battles/leave/99999999/", {"user_id": stranger.id}).status_code == 404
    assert len(members(battle)) == 2


# --- start ------------------------------------------------------------------


@pytest.mark.parametrize("minutes", [5, 15, 120])
def test_start_activates_the_battle_and_the_deadline_is_start_plus_minutes(
    internal, make_battle, make_user, minutes
):
    creator, rival = make_user(), make_user()
    battle = make_battle(creator=creator, duration=minutes)
    spectator = make_user()
    for user, body in ((creator, {}), (rival, {}), (spectator, {"role": "spectator"})):
        join(internal, battle, user, **body)

    response = start(internal, battle, creator)

    battle.refresh_from_db()
    assert response.status_code == 200
    assert set(response.json()) == {"status", "deadline"}
    assert response.json()["status"] == "success"
    assert battle.status == "active"
    # epoch seconds, `minutes` after the start: not seconds, not milliseconds
    assert response.json()["deadline"] == pytest.approx(battle.start_time.timestamp() + minutes * 60)
    assert {status for *_, status in members(battle)} == {"playing"}


def test_only_the_creator_starts_the_battle(internal, duel):
    battle, _, rival = duel

    response = start(internal, battle, rival)

    assert response.status_code == 403
    assert Battle.objects.get(pk=battle.pk).status == "pending"


@pytest.mark.parametrize("kind", ["1v1", "group"])
def test_start_needs_two_players_in_both_kinds_of_battle(internal, make_battle, make_user, kind):
    creator = make_user()
    battle = make_battle(creator=creator, type=kind, max_participants=2 if kind == "1v1" else 5)
    assert start(internal, battle, creator).status_code == 409  # nobody yet

    join(internal, battle, creator)
    join(internal, battle, make_user(), role="spectator")  # a spectator is no player
    response = start(internal, battle, creator)

    assert response.status_code == 409
    assert Battle.objects.get(pk=battle.pk).start_time is None

    join(internal, battle, make_user())
    assert start(internal, battle, creator).status_code == 200


def test_a_group_battle_starts_with_any_number_of_players_from_two(internal, make_battle, make_user):
    creator = make_user()
    battle = make_battle(creator=creator, type="group", max_participants=10)
    for user in (creator, make_user(), make_user(), make_user()):
        join(internal, battle, user)

    assert start(internal, battle, creator).status_code == 200


def test_a_second_start_is_409_and_keeps_the_start_time(internal, duel):
    battle, creator, _ = duel
    assert start(internal, battle, creator).status_code == 200
    first = Battle.objects.get(pk=battle.pk).start_time

    again = start(internal, battle, creator)

    assert again.status_code == 409
    assert Battle.objects.get(pk=battle.pk).start_time == first


def test_start_of_a_finished_or_unknown_battle(internal, running_duel):
    battle, creator, _ = running_duel
    assert finish(internal, battle, creator).status_code == 200

    assert start(internal, battle, creator).status_code == 409
    assert internal("patch", "/internal/battles/start/99999999/", {"user_id": creator.id}).status_code == 404


# --- finish -----------------------------------------------------------------


def test_finish_keeps_every_participant_and_records_the_winner(
    internal, running_duel, make_user
):
    battle, creator, rival = running_duel
    watcher = make_user()
    join(internal, battle, watcher)

    response = finish(internal, battle, rival)

    battle.refresh_from_db()
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert (battle.status, battle.winner_id) == ("finished", rival.id)
    assert battle.end_time is not None
    assert members(battle) == [
        (creator.id, "player", "finished"),
        (rival.id, "player", "finished"),
        (watcher.id, "spectator", "finished"),
    ]


def test_time_up_is_a_draw(internal, running_duel):
    battle, _, _ = running_duel

    response = finish(internal, battle, None)

    battle.refresh_from_db()
    assert response.status_code == 200
    assert (battle.status, battle.winner_id) == ("finished", None)
    assert len(members(battle)) == 2


def test_a_repeated_finish_is_a_noop_and_another_result_is_409(internal, running_duel):
    battle, creator, rival = running_duel
    assert finish(internal, battle, creator).status_code == 200
    ended = Battle.objects.get(pk=battle.pk).end_time

    assert finish(internal, battle, creator).status_code == 200  # FastAPI retries a lost answer
    assert finish(internal, battle, rival).status_code == 409
    assert finish(internal, battle, None).status_code == 409

    battle.refresh_from_db()
    assert (battle.winner_id, battle.end_time) == (creator.id, ended)


def test_a_draw_cannot_be_turned_into_a_win(internal, running_duel):
    battle, creator, _ = running_duel
    assert finish(internal, battle, None).status_code == 200

    assert finish(internal, battle, None).status_code == 200
    assert finish(internal, battle, creator).status_code == 409
    assert Battle.objects.get(pk=battle.pk).winner_id is None


def test_the_winner_must_be_a_player_of_the_battle(internal, running_duel, make_user):
    battle, _, _ = running_duel
    spectator, outsider = make_user(), make_user()
    join(internal, battle, spectator)

    for winner_id in (spectator.id, outsider.id, 99999999):
        response = internal("patch", f"/internal/battles/finish/{battle.id}/", {"winner_id": winner_id})
        assert response.status_code == 400, winner_id
        assert "winner_id" in response.json()

    battle.refresh_from_db()
    assert (battle.status, battle.winner_id, battle.end_time) == ("active", None, None)
    assert {status for *_, status in members(battle)} == {"playing"}


def test_finish_needs_the_winner_id_key(internal, running_duel):
    battle, _, _ = running_duel

    response = internal("patch", f"/internal/battles/finish/{battle.id}/", {})

    assert response.status_code == 400
    assert Battle.objects.get(pk=battle.pk).status == "active"


def test_a_pending_battle_can_be_closed_and_then_nobody_joins(internal, make_battle, make_user):
    creator, other = make_user(), make_user()
    battle = make_battle(creator=creator)
    join(internal, battle, creator)

    assert finish(internal, battle, creator).status_code == 200
    assert join(internal, battle, other).status_code == 409
    assert internal("patch", "/internal/battles/finish/99999999/", {"winner_id": None}).status_code == 404


# --- delete -----------------------------------------------------------------


def test_delete_removes_a_pending_battle_with_everything_that_hangs_on_it(internal, duel):
    battle, creator, _ = duel
    Submission.objects.create(battle=battle, user=creator, code="print(1)", status="failed")

    response = internal("delete", f"/internal/battles/delete/{battle.id}/")

    assert response.status_code == 204
    assert not Battle.objects.filter(pk=battle.pk).exists()
    assert not Participant.objects.filter(battle_id=battle.pk).exists()
    assert not Submission.objects.filter(battle_id=battle.pk).exists()


def test_delete_leaves_running_and_finished_battles_alone(internal, running_duel):
    battle, creator, _ = running_duel
    path = f"/internal/battles/delete/{battle.id}/"

    assert internal("delete", path).status_code == 409
    assert finish(internal, battle, creator).status_code == 200
    response = internal("delete", path)

    assert response.status_code == 409  # J10
    assert response.json() == {"detail": "Battle is not pending and cannot be deleted"}
    assert Battle.objects.filter(pk=battle.pk).exists()
    assert len(members(battle)) == 2


# --- internal list ----------------------------------------------------------


def test_internal_list_has_ids_and_filters_by_status(internal, make_battle):
    pending, active, finished = make_battle(), make_battle(status="active"), make_battle(status="finished")

    everything = internal("get", "/internal/battles/").json()
    only_active = internal("get", "/internal/battles/?status=active").json()

    assert {b["id"] for b in everything} == {pending.id, active.id, finished.id}
    assert [b["id"] for b in only_active] == [active.id]
    assert {"id", "status", "type", "task", "max_participants", "is_private"} <= set(only_active[0])
    assert not {"invite_code", "creator"} & set(only_active[0])  # still hidden
    for bogus in ("?status=bogus", "?status="):
        response = internal("get", f"/internal/battles/{bogus}")
        assert response.status_code == 400
        assert "status" in response.json()


# --- events -----------------------------------------------------------------


def test_join_and_leave_announce_the_lobby_after_the_commit(internal, make_battle, make_user, published):
    battle, user = make_battle(), make_user()

    join(internal, battle, user)
    leave(internal, battle, user)

    assert published == [
        (battle.id, {"event": "lobby_update", "data": {"participants_count": 1, "task_id": battle.task}}),
        (battle.id, {"event": "lobby_update", "data": {"participants_count": 0}}),
    ]


def test_a_reconnect_announces_the_lobby_again(internal, duel, published):
    """A new socket learns the task from lobby_update, a repeated join must send it too."""
    battle, creator, _ = duel
    published.clear()

    join(internal, battle, creator)

    assert [event["data"]["task_id"] for _, event in published] == [battle.task]


def test_nothing_is_announced_for_a_join_that_is_rolled_back(
    make_battle, make_user, published, django_capture_on_commit_callbacks
):
    battle, user = make_battle(), make_user()

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(RuntimeError), transaction.atomic():
            join_battle(battle_id=battle.id, user_id=user.id)
            raise RuntimeError("the surrounding transaction fails")

    assert (callbacks, published) == ([], [])
    assert not battle.participants.exists()


def test_django_sends_only_events_the_frontend_knows(internal, make_battle, make_user, published):
    creator, rival = make_user(), make_user()
    battle = make_battle(creator=creator)
    for user in (creator, rival):
        join(internal, battle, user)
    start(internal, battle, creator)
    leave(internal, battle, rival)
    finish(internal, battle, creator)

    # FastAPI sends battle_started / battle_finished itself, the rest was never shown by the UI
    assert {event["event"] for _, event in published} == {"lobby_update"}


def test_a_redis_outage_does_not_fail_join_or_leave(
    redis_down, internal, make_battle, make_user, caplog
):
    battle, user = make_battle(), make_user()

    with caplog.at_level(logging.WARNING, logger="infrastructure.messaging.battle_events"):
        joined = join(internal, battle, user)
        left = leave(internal, battle, user)

    assert (joined.status_code, left.status_code) == (200, 200)
    warnings = [r.getMessage() for r in caplog.records if "Could not publish" in r.getMessage()]
    assert len(warnings) == 2
    assert all("lobby_update" in message for message in warnings)


# --- races ------------------------------------------------------------------


def race(battle, bodies):
    """Run join_battle for every body in its own thread (and DB connection) at the same moment."""
    barrier = threading.Barrier(len(bodies))

    def attempt(body):
        try:
            barrier.wait(timeout=10)
            return join_battle(battle_id=battle.id, **body).participant.role
        except APIException as exc:
            return exc.status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(len(bodies)) as pool:
        return list(pool.map(attempt, bodies))


@pytest.mark.django_db(transaction=True)
def test_the_last_free_place_goes_to_exactly_one_player(make_battle, make_user):
    creator = make_user()
    battle = make_battle(creator=creator)  # 1v1, one place left once the creator is in
    join_battle(battle_id=battle.id, user_id=creator.id)
    contenders = [make_user() for _ in range(6)]

    results = race(battle, [{"user_id": u.id, "role": "player"} for u in contenders])

    assert sorted(results, key=str) == [409] * 5 + ["player"]
    assert battle.participants.filter(role="player").count() == 2


@pytest.mark.django_db(transaction=True)
def test_without_a_role_the_loser_of_the_race_becomes_a_spectator(make_battle, make_user):
    creator = make_user()
    battle = make_battle(creator=creator)
    join_battle(battle_id=battle.id, user_id=creator.id)
    contenders = [make_user() for _ in range(6)]

    results = race(battle, [{"user_id": u.id} for u in contenders])

    assert sorted(results) == ["player"] + ["spectator"] * 5
    assert battle.participants.filter(role="player").count() == 2


@pytest.mark.django_db(transaction=True)
def test_one_user_in_several_tabs_at_once_gets_one_row(make_battle, make_user):
    user = make_user()
    battle = make_battle()

    results = race(battle, [{"user_id": user.id}] * 5)

    assert results == ["player"] * 5
    assert battle.participants.count() == 1
