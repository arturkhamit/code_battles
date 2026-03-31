from django.conf import settings
from django.db import models


class Submission(models.Model):
    battle = models.ForeignKey(
        "battles.Battle", on_delete=models.CASCADE, related_name="submission"
    )
    author = models.ForeignKey(
        "battles.Participant", on_delete=models.CASCADE, related_name="submissions"
    )
    date = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=20)
    code = models.TextField(max_length=65535)

    # maybe add status: draft/final/invalid
