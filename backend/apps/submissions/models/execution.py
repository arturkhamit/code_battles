from django.db import models


class Execution(models.Model):
    submission = models.OneToOneField(
        "submissions.Submission", on_delete=models.DO_NOTHING, related_name="execution"
    )
    status = models.CharField(
        max_length=20,
        default="queued",  # queued/running/ok/fail/timeout (not final)
    )
    execution_time = models.DurationField(blank=True)
