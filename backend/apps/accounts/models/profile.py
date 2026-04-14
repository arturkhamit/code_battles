from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.URLField(
        default="https://gogle.com/svg.png",
    )
    rating = models.IntegerField(null=True, default=1000)
    preferred_language = models.CharField(null=True, blank=True)

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"

    def __str__(self):
        return f"id -- {self.pk}\nuser -- {self.user}"
