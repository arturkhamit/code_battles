"""manage.py import_tasks [path]: load tasks from a JSON Lines file into the Task table.

The file (one task per line, up to 17 MB a line, 93 MB in total) is read line by line and
written in batches. A task's id is its 1-based line number, so Battle.task keeps pointing at
the same problem and running the command again updates the same rows (upsert, no duplicates).
"""

import json
import logging
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, reset_queries

from apps.tasks.models import Task
from apps.tasks.models.task import empty_tests
from apps.tasks.serializers import TaskImportSerializer

logger = logging.getLogger(__name__)

# backend/apps/tasks/management/commands/import_tasks.py -> backend/tests/tests.json
DEFAULT_PATH = Path(__file__).resolve().parents[4] / "tests" / "tests.json"

# Django writes a multi-row bulk_create through UNNEST, and psycopg then needs ~30x the size of
# the JSON values in memory (a batch with the 17 MB task took 550 MB). So a multi-row batch is
# capped at BATCH_CHARS of file text (50 ordinary tasks are ~1 MB); a huge task goes alone.
BATCH_ROWS = 50
BATCH_CHARS = 1_000_000

# every column except the pk and the ones Postgres computes (difficulty_label, ...);
# `solutions` and `incorrect_solutions` are not columns, so dropped
FIELDS = [f.name for f in Task._meta.concrete_fields if not f.primary_key and not f.generated]
TEST_FIELDS = ("public_tests", "private_tests", "generated_tests")


class Command(BaseCommand):
    help = "Import tasks from a JSON Lines file into the Task table. Safe to run again."

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            nargs="?",
            type=Path,
            default=DEFAULT_PATH,
            help="JSON Lines file (default: backend/tests/tests.json)",
        )

    def handle(self, *args, path, **options):
        if not path.is_file():
            raise CommandError(f"File not found: {path}")

        started = time.monotonic()
        imported = skipped = batch_chars = 0
        batch = []
        with path.open(encoding="utf-8") as lines:
            for task_id, line in enumerate((ln for ln in lines if ln.strip()), start=1):
                task = self._parse(task_id, line)
                if task is None:
                    skipped += 1
                    continue
                if batch and batch_chars + len(line) > BATCH_CHARS:
                    imported += self._save(batch)
                    batch, batch_chars = [], 0
                batch.append(task)
                batch_chars += len(line)
                if len(batch) >= BATCH_ROWS or batch_chars >= BATCH_CHARS:
                    imported += self._save(batch)
                    batch, batch_chars = [], 0
        imported += self._save(batch)
        self._reset_sequence()

        self.stdout.write(
            f"Imported {imported} tasks, skipped {skipped}, "
            f"in {time.monotonic() - started:.1f} s"
        )

    @staticmethod
    def _parse(task_id: int, line: str) -> Task | None:
        """One line -> unsaved Task, or None (logged) if the line is not a valid task."""
        try:
            serializer = TaskImportSerializer(data=json.loads(line))
            valid = serializer.is_valid()
            reason = str(serializer.errors) if not valid else ""
        except ValueError as exc:  # json.JSONDecodeError
            valid, reason = False, f"not JSON: {exc}"
        if not valid:
            logger.warning("import_tasks: row %d skipped: %.500s", task_id, reason)
            return None

        data = serializer.validated_data
        values = {name: data[name] for name in FIELDS if name in data}
        for name in TEST_FIELDS:
            values[name] = data.get(name) or empty_tests()  # null in the file -> no tests
        return Task(id=task_id, **values)

    @staticmethod
    def _save(batch: list[Task]) -> int:
        if batch:
            Task.objects.bulk_create(
                batch, update_conflicts=True, unique_fields=["id"], update_fields=FIELDS
            )
            reset_queries()  # DEBUG=True keeps every executed INSERT, values included
        return len(batch)

    @staticmethod
    def _reset_sequence() -> None:
        """Rows were inserted with explicit ids: move the id sequence past them."""
        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(no_style(), [Task]):
                cursor.execute(sql)
