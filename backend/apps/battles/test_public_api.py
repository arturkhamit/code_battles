# ruff: noqa: S101, S106
"""The public side of battles (JWT): create, the open lobbies, lookup by invite code.
Needs Postgres and Redis (see pytest.ini)."""

import logging
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.battles.models import Battle, Participant
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db

DROP = object()  # leave the key out of the request body
VALID = {"type": "1v1", "task": 1, "duration": 15, "max_participants": 2}


def create(api, user, **changes):
    body = {k: v for k, v in {**VALID, **changes}.items() if v is not DROP}
    api.force_authenticate(user)
    return api.post("/api/battles/create/", body, format="json")


@pytest.fixture
def logged_in(api, user):
    api.force_authenticate(user)
    return api


# --- create -----------------------------------------------------------------


def test_create_returns_the_battle_with_its_invite_code(api, user, task):
    response = create(api, user)

    assert response.status_code == 201
    body = response.json()
    battle = Battle.objects.get()
    assert body == {
        "id": battle.id,
        "status": "pending",
        "ranked": False,
        "type": "1v1",
        "task": 1,
        "creator": user.id,
        "duration": 15,
        "max_participants": 2,
        "is_private": False,
        "invite_code": battle.invite_code,
        "created_at": body["created_at"],
    }
    assert len(battle.invite_code) == 6
    assert battle.duration == 15


def test_create_takes_the_creator_from_the_token_not_from_the_body(api, user, task, make_user):
    other = make_user()
    response = create(api, user, creator=other.id)
    assert response.json()["creator"] == user.id


def test_a_1v1_always_has_two_places_whatever_the_client_says(api, user, task):
    for sent in (DROP, 2, 5, 10):
        assert create(api, user, max_participants=sent).json()["max_participants"] == 2


def test_a_group_battle_takes_2_to_10_players_and_defaults_to_10(api, user, task):
    assert create(api, user, type="group", max_participants=DROP).json()["max_participants"] == 10
    for places in (2, 3, 10):
        response = create(api, user, type="group", max_participants=places)
        assert (response.status_code, response.json()["max_participants"]) == (201, places)
    for places in (1, 0, -3, 11, None, "many", 2.5):
        response = create(api, user, type="group", max_participants=places)
        assert response.status_code == 400, places
        assert "max_participants" in response.json()
    assert Battle.objects.count() == 4


@pytest.mark.parametrize("minutes", [5, 6, 60, 120, "15", 15.0])
def test_create_accepts_whole_minutes_from_5_to_120(api, user, task, minutes):
    response = create(api, user, duration=minutes)
    assert response.status_code == 201
    assert response.json()["duration"] == int(float(minutes))


@pytest.mark.parametrize("minutes", [None, 0, -5, 4, 121, 3600, 0.1, 5.5, "abc", "", True, [], DROP])
def test_create_rejects_a_bad_duration(api, user, task, minutes):
    response = create(api, user, duration=minutes)  # V1, V4, V5, V6a, V6b
    assert response.status_code == 400
    assert "duration" in response.json()
    assert not Battle.objects.exists()


@pytest.mark.parametrize("task_id", [0, -1, 999999, None, "x", 1.5, DROP])
def test_create_rejects_a_task_that_does_not_exist(api, user, task, task_id):
    response = create(api, user, task=task_id)  # V3a, V3b
    assert response.status_code == 400
    assert "task" in response.json()
    assert not Battle.objects.exists()


def test_create_checks_the_task_in_the_task_table(api, user):
    assert create(api, user).status_code == 400  # no tasks imported yet
    Task.objects.create(id=1, name="a", description="d")
    assert create(api, user).status_code == 201


@pytest.mark.parametrize("kind", [None, "", "battle-royale", "training", "GROUP", 1, DROP])
def test_create_rejects_an_unknown_type(api, user, task, kind):
    response = create(api, user, type=kind)
    assert response.status_code == 400
    assert "type" in response.json()


def test_create_takes_private_and_ranked_flags(api, user, task):
    plain = create(api, user).json()
    flagged = create(api, user, is_private=True, ranked=True).json()

    assert (plain["is_private"], plain["ranked"]) == (False, False)
    assert (flagged["is_private"], flagged["ranked"]) == (True, True)
    for field in ("is_private", "ranked"):
        for bad in (None, "maybe", [], {}):
            assert create(api, user, **{field: bad}).status_code == 400, (field, bad)


def test_create_is_for_logged_in_users_only(api, task):
    assert api.post("/api/battles/create/", VALID, format="json").status_code == 401


def test_invite_codes_are_unique_and_a_collision_is_retried(api, user, task, monkeypatch):
    taken = create(api, user).json()["invite_code"]
    codes = iter([taken, taken, "fresh1"])  # two collisions, then a free code
    monkeypatch.setattr("secrets.token_urlsafe", lambda nbytes: next(codes))

    response = create(api, user)

    assert response.status_code == 201
    assert response.json()["invite_code"] == "fresh1"
    assert sorted(Battle.objects.values_list("invite_code", flat=True)) == sorted([taken, "fresh1"])


def test_create_gives_up_with_409_when_no_free_invite_code_turns_up(api, user, task, monkeypatch):
    taken = create(api, user).json()["invite_code"]
    monkeypatch.setattr("secrets.token_urlsafe", lambda nbytes: taken)

    response = create(api, user)

    assert response.status_code == 409
    assert Battle.objects.count() == 1


def test_create_survives_a_redis_outage(redis_down, api, user, task, caplog):
    with caplog.at_level(logging.WARNING, logger="apps.battles.throttles"):
        response = create(api, user)  # RD1: no 500 ...

    assert response.status_code == 201
    assert Battle.objects.count() == 1  # ... and RD1b: no half-made battle
    assert any("Redis is unavailable" in r.getMessage() for r in caplog.records)


# --- open lobbies -----------------------------------------------------------


def add_players(battle, users, role="player"):
    for user in users:
        Participant.objects.create(battle=battle, user=user, role=role)


@pytest.fixture
def lobbies(make_battle, make_user):
    """Oldest first: private, started, finished, full, plus three joinable ones."""
    users = [make_user() for _ in range(4)]
    made = {
        "private": make_battle(is_private=True),
        "active": make_battle(status="active"),
        "finished": make_battle(status="finished"),
        "full": make_battle(),
        "one_of_two": make_battle(),
        "empty_group": make_battle(type="group", max_participants=4),
        "group_of_three": make_battle(type="group", max_participants=4),
    }
    add_players(made["full"], users[:2])
    add_players(made["one_of_two"], users[:1])
    add_players(made["group_of_three"], users[:3])
    add_players(made["group_of_three"], users[3:], role="spectator")  # watchers take no place
    return made


def test_open_lists_public_pending_lobbies_with_free_places_newest_first(logged_in, lobbies):
    response = logged_in.get("/api/battles/open/")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert [b["id"] for b in body["results"]] == [
        lobbies["group_of_three"].id,
        lobbies["empty_group"].id,
        lobbies["one_of_two"].id,
    ]
    assert body["count"] == 3


def test_open_item_has_what_a_lobby_card_needs(logged_in, lobbies):
    battle = lobbies["one_of_two"]

    item = next(b for b in logged_in.get("/api/battles/open/").json()["results"] if b["id"] == battle.id)

    assert item == {
        "id": battle.id,
        "type": "1v1",
        "task": {"id": 1, "name": "162_A", "difficulty_label": "easy"},
        "duration": 15,
        "max_participants": 2,
        "players_count": 1,
        "creator_username": battle.creator.username,
        "created_at": item["created_at"],
        "invite_code": battle.invite_code,
    }


def test_open_counts_players_only(logged_in, lobbies):
    results = {b["id"]: b for b in logged_in.get("/api/battles/open/").json()["results"]}
    group = results[lobbies["group_of_three"].id]
    assert (group["players_count"], group["max_participants"]) == (3, 4)


def test_open_pages_with_limit_and_offset_up_to_50(logged_in, make_battle):
    battles = [make_battle() for _ in range(60)]

    default = logged_in.get("/api/battles/open/").json()
    capped = logged_in.get("/api/battles/open/?limit=1000").json()
    tail = logged_in.get("/api/battles/open/?limit=50&offset=50").json()
    odd = logged_in.get("/api/battles/open/?limit=-1&offset=x")

    assert (default["count"], len(default["results"])) == (60, 20)
    assert len(capped["results"]) == 50
    assert default["next"].endswith("/api/battles/open/?limit=20&offset=20")
    assert [b["id"] for b in tail["results"]] == [b.id for b in reversed(battles)][50:]
    assert odd.status_code == 200
    assert len(odd.json()["results"]) == 20  # bad values fall back to the defaults


def test_open_needs_a_few_queries_whatever_the_size(logged_in, make_battle, django_assert_max_num_queries):
    for _ in range(25):
        make_battle()

    with django_assert_max_num_queries(3):  # count, page, tasks
        assert logged_in.get("/api/battles/open/?limit=25").status_code == 200


def test_open_never_loads_the_task_tests(logged_in, make_battle):
    make_battle()

    with CaptureQueriesContext(connection) as queries:
        logged_in.get("/api/battles/open/")

    task_selects = [q["sql"] for q in queries if 'FROM "tasks_task"' in q["sql"]]
    assert task_selects
    assert not any("_tests" in sql for sql in task_selects)  # megabytes per task


def test_open_is_for_logged_in_users_only(api, lobbies):
    assert api.get("/api/battles/open/").status_code == 401


def age(battle, minutes):
    Battle.objects.filter(pk=battle.pk).update(created_at=timezone.now() - timedelta(minutes=minutes))


def test_open_hides_lobbies_older_than_30_minutes(logged_in, make_battle):
    fresh, almost, stale = make_battle(), make_battle(), make_battle()
    age(almost, 29)
    age(stale, 31)

    ids = [b["id"] for b in logged_in.get("/api/battles/open/").json()["results"]]

    assert ids == [fresh.id, almost.id]


def test_expire_pending_battles_deletes_only_old_pending_ones(make_battle, make_user):
    old_pending, new_pending, old_active = make_battle(), make_battle(), make_battle(status="active")
    add_players(old_pending, [make_user()])
    for battle in (old_pending, old_active):
        age(battle, 61)
    age(new_pending, 59)

    out = StringIO()
    call_command("expire_pending_battles", stdout=out)

    assert set(Battle.objects.values_list("id", flat=True)) == {new_pending.id, old_active.id}
    assert not Participant.objects.filter(battle_id=old_pending.id).exists()
    assert "Deleted 1 " in out.getvalue()

    call_command("expire_pending_battles", "--minutes", "30", stdout=out)
    assert set(Battle.objects.values_list("id", flat=True)) == {old_active.id}
    assert "Deleted 1 " in out.getvalue().splitlines()[-1]


# --- invite lookup ----------------------------------------------------------


def test_invite_describes_the_battle_of_a_public_or_private_code(logged_in, make_battle, make_user):
    public, private = make_battle(), make_battle(is_private=True, type="group", max_participants=6)
    add_players(private, [make_user(), make_user()])

    for battle in (public, private):
        response = logged_in.get(f"/api/battles/invite/{battle.invite_code}/")
        assert response.status_code == 200
        assert response.json() == {
            "id": battle.id,
            "type": battle.type,
            "status": "pending",
            "task": {"id": 1, "name": "162_A", "difficulty_label": "easy"},
            "players_count": battle.participants.count(),
            "max_participants": battle.max_participants,
            "is_private": battle.is_private,
        }


def test_invite_also_answers_for_a_started_or_finished_battle(logged_in, make_battle):
    for status in ("active", "finished"):
        battle = make_battle(status=status)
        response = logged_in.get(f"/api/battles/invite/{battle.invite_code}/")
        assert (response.status_code, response.json()["status"]) == (200, status)


@pytest.mark.parametrize("code", ["nope12", "x", "toolongcode", "a b", "%00", "ab%2Fcd", "é" * 3])
def test_invite_with_an_unknown_or_malformed_code_is_404(logged_in, make_battle, code):
    make_battle()
    response = logged_in.get(f"/api/battles/invite/{code}/")
    assert response.status_code == 404


def test_invite_is_for_logged_in_users_only(api, make_battle):
    battle = make_battle()
    assert api.get(f"/api/battles/invite/{battle.invite_code}/").status_code == 401


def test_invite_lookups_are_limited_to_30_a_minute(logged_in, make_battle):
    battle = make_battle()
    url = f"/api/battles/invite/{battle.invite_code}/"

    assert all(logged_in.get(url).status_code == 200 for _ in range(30))
    throttled = logged_in.get(url)

    assert throttled.status_code == 429
    assert int(throttled["Retry-After"]) > 0


def test_invite_survives_a_redis_outage(redis_down, logged_in, make_battle):
    battle = make_battle()
    assert logged_in.get(f"/api/battles/invite/{battle.invite_code}/").status_code == 200
