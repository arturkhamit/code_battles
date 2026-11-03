import apps.battles.models.battle
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("battles", "0017_dedupe_participants_and_invite_codes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="battle",
            name="is_private",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="battle",
            name="invite_code",
            field=models.CharField(
                default=apps.battles.models.battle.generate_invite_code,
                max_length=6,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="participant",
            name="status",
            field=models.CharField(
                choices=[
                    ("waiting", "Waiting"),
                    ("playing", "Playing"),
                    ("finished", "Finished"),
                    ("disconnected", "Disconnected"),
                ],
                default="waiting",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(
                fields=("battle", "user"), name="unique_participant_per_battle"
            ),
        ),
    ]
