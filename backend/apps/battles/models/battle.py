from django.conf import settings
from django.db import models


class Battle(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ACTIVE = "active"
        FINISHED = "finished"
        # (maybe add paused)

    class Type(models.TextChoices):
        DUEL = "1v1"
        # add sumtin (important)

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
    duration = models.FloatField(blank=True, null=True)
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
    invite_code = models.CharField(max_length=6, blank=True, default=None)

    class Meta:
        verbose_name = "Battle"
        verbose_name_plural = "Battles"

    def __str__(self):
        return f"id -- {self.pk}\nstart -- {self.start_time}\nproblem -- {self.task}"
