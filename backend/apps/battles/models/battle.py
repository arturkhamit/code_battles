import secrets

from django.conf import settings
from django.db import models


def generate_invite_code() -> str:
    """6 URL-safe characters. The column is unique; create_battle retries on a collision."""
    return secrets.token_urlsafe(4)


class Battle(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ACTIVE = "active"
        FINISHED = "finished"
        # (maybe add paused)

    class Type(models.TextChoices):
        DUEL = "1v1"
        GROUP = "group"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    ranked = models.BooleanField(default=False)
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.DUEL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    duration = models.FloatField(blank=True, null=True)  # minutes (the API accepts 5..120)
    task = models.IntegerField()
    max_participants = models.IntegerField()
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="creator",
        blank=True,
        default=None,
    )
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="winner",
        blank=True,
        null=True,
        default=None,
    )
    # private: not in the open list, joining needs invite_code (the creator and members are exempt)
    is_private = models.BooleanField(default=False)
    invite_code = models.CharField(
        max_length=6, unique=True, default=generate_invite_code
    )

    class Meta:
        verbose_name = "Battle"
        verbose_name_plural = "Battles"

    def __str__(self):
        return f"id -- {self.pk}\nstart -- {self.start_time}\nproblem -- {self.task}"
