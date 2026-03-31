from django.conf import settings
from django.db import models


class Participant(models.Model):
    class Role(models.TextChoices):
        PLAYER = "player"
        SPECTATOR = "spectator"

    class Status(models.TextChoices):
        WAITING = "waiting"
        PLAYING = "playing"
        FINISHED = "finished"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participant"
    )
    battle = models.ForeignKey(
        "battles.Battle", on_delete=models.CASCADE, related_name="participants"
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PLAYER,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    score = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Participant"
        verbose_name_plural = "Participants"
