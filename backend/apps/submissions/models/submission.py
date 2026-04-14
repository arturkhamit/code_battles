from django.db import models
from django.conf import settings


class Submission(models.Model):
    battle = models.ForeignKey('battles.Battle', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    code = models.TextField()

    STATUS_CHOICES = [
        ('success', 'success'),
        ('failed', 'failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Submission by {self.user.username} at {self.created_at}"