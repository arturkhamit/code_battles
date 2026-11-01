import json
import logging
from datetime import datetime, timezone

# Attributes every LogRecord has; anything else came from `extra=` and is logged too.
# Django also attaches `request` (its repr includes the query string) and `server_time`
# (duplicates `ts`): left out.
_SKIPPED_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message",
    "asctime",
    "request",
    "server_time",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per line: ts, level, logger, message (+ exc_info, extras)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        for key, value in vars(record).items():
            if key not in _SKIPPED_ATTRS:
                payload[key] = value
        return json.dumps(payload, default=str)
