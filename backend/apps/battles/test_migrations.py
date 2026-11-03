# ruff: noqa: S101, S106
"""Migrations 0017/0018 on a database that already holds duplicates: only the surplus goes."""

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("battles", "0016_alter_battle_type")]
AFTER = [("battles", "0018_open_lobbies_unique_participants")]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps  # the models as they were then


@pytest.mark.django_db(transaction=True)
def test_duplicates_are_removed_before_the_unique_constraints_arrive():
    old = migrate(BEFORE)
    try:
        User, Battle, Participant = (
            old.get_model(app, model)
            for app, model in (("accounts", "User"), ("battles", "Battle"), ("battles", "Participant"))
        )
        u1 = User.objects.create(username="u1", email="u1@example.com", password="x")
        u2 = User.objects.create(username="u2", email="u2@example.com", password="x")
        new_battle = lambda code: Battle.objects.create(  # noqa: E731
            creator=u1, task=1, max_participants=2, invite_code=code
        )
        b1, b2, b3, b4 = new_battle("dup"), new_battle("dup"), new_battle(""), new_battle("ok")

        def row(battle, user, role):
            return Participant.objects.create(battle=battle, user=user, role=role).pk

        row(b1, u1, "spectator")
        first_player = row(b1, u1, "player")  # wins over the older spectator row ...
        row(b1, u1, "player")  # ... and over the younger player row
        oldest_spectator = row(b1, u2, "spectator")  # only spectators: the oldest stays
        row(b1, u2, "spectator")
        single = row(b2, u1, "player")  # no duplicate: untouched
        row(b3, u2, "spectator")
        later_player = row(b3, u2, "player")  # the player is younger but still wins
        assert Participant.objects.count() == 8

        migrate(AFTER)

        from apps.battles.models import Battle as NewBattle  # noqa: PLC0415
        from apps.battles.models import Participant as NewParticipant  # noqa: PLC0415

        assert set(NewParticipant.objects.values_list("id", flat=True)) == {
            first_player, oldest_spectator, single, later_player,
        }  # fmt: skip
        assert sorted(NewParticipant.objects.values_list("battle_id", "user_id")) == sorted(
            {(b1.pk, u1.pk), (b1.pk, u2.pk), (b2.pk, u1.pk), (b3.pk, u2.pk)}
        )
        codes = dict(NewBattle.objects.values_list("id", "invite_code"))
        assert codes[b1.pk] == "dup"  # the oldest battle keeps its code
        assert codes[b4.pk] == "ok"
        assert codes[b2.pk] not in ("", "dup")
        assert codes[b3.pk] != ""
        assert len(set(codes.values())) == 4
        assert all(len(code) <= 6 for code in codes.values())
        assert NewBattle.objects.get(pk=b1.pk).is_private is False

        with pytest.raises(IntegrityError), transaction.atomic():
            NewParticipant.objects.create(battle_id=b1.pk, user_id=u1.pk)
        with pytest.raises(IntegrityError), transaction.atomic():
            NewBattle.objects.create(creator_id=u1.pk, task=1, max_participants=2, invite_code="ok")
    finally:
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        migrate(latest)
