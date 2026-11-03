"""Data only: make the rows fit the constraints that 0018 adds.

A migration of its own, so the data is committed before 0018 runs its ALTER TABLEs.

- participants: one row per (battle, user). The player row wins over a spectator row, then
  the lowest id. Only the surplus duplicates are deleted, every other row is untouched.
- battles: unique, non-empty invite_code. The first battle (lowest id) keeps its code,
  empty and repeated codes get a fresh one.
"""

import secrets

from django.db import migrations
from django.db.models import Case, F, IntegerField, When, Window
from django.db.models.functions import RowNumber


def dedupe_participants(apps, schema_editor):
    Participant = apps.get_model("battles", "Participant")
    ranked = Participant.objects.annotate(
        rank=Window(
            RowNumber(),
            partition_by=[F("battle_id"), F("user_id")],
            order_by=[
                Case(
                    When(role="player", then=0), default=1, output_field=IntegerField()
                ).asc(),
                F("id").asc(),
            ],
        )
    )
    duplicate_ids = list(ranked.filter(rank__gt=1).values_list("id", flat=True))
    Participant.objects.filter(id__in=duplicate_ids).delete()


def fill_invite_codes(apps, schema_editor):
    Battle = apps.get_model("battles", "Battle")
    taken = set(Battle.objects.values_list("invite_code", flat=True))  # a new code avoids all of them
    kept = set()
    for battle_id, code in Battle.objects.order_by("id").values_list("id", "invite_code"):
        if code and code not in kept:
            kept.add(code)
            continue
        while (code := secrets.token_urlsafe(4)) in taken:  # same format as generate_invite_code
            pass
        taken.add(code)
        kept.add(code)
        Battle.objects.filter(id=battle_id).update(invite_code=code)


class Migration(migrations.Migration):

    dependencies = [
        ("battles", "0016_alter_battle_type"),
    ]

    operations = [
        # only the duplicates are lost for good; going back leaves the remaining rows as they are
        migrations.RunPython(dedupe_participants, migrations.RunPython.noop),
        migrations.RunPython(fill_invite_codes, migrations.RunPython.noop),
    ]
