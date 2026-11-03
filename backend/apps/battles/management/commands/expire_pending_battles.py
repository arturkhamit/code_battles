"""manage.py expire_pending_battles [--minutes 60]: delete pending battles older than N minutes.

A lobby created over HTTP and never opened over WS gets no idle timer, so it would stay forever.
Meant for cron.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.battles.models import Battle


class Command(BaseCommand):
    help = "Delete pending battles older than --minutes (default 60)."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=60)

    def handle(self, *args, minutes, **options):
        cutoff = timezone.now() - timedelta(minutes=minutes)
        deleted = 0
        stale = Battle.objects.filter(status=Battle.Status.PENDING, created_at__lt=cutoff)
        for battle in stale.iterator():
            battle.delete()  # per object: cascades and delete signals run as in the app
            deleted += 1
        self.stdout.write(f"Deleted {deleted} pending battle(s) older than {minutes} min.")
