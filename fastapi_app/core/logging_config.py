import json
import logging
import re
import sys
from datetime import datetime, timezone

from core.config import settings

# Attributes every LogRecord has; anything else came from `extra=` (battle_id, user_id,
# verdict, ms, ...) and is logged too. Same format as backend/config/logging_json.py.
_SKIPPED_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message",
    "asctime",
}


_TOKEN_IN_QUERY = re.compile(r"([?&]token=)[^&\s\"']*")


class RedactTokenFilter(logging.Filter):
    """uvicorn logs WS paths with the query: `/ws/battle/1?token=eyJ...` -> `token=***`."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "token=" in message:
            record.msg, record.args = _TOKEN_IN_QUERY.sub(r"\1***", message), ()
        return True


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


def setup_logging():
    """JSON lines on stdout, level from LOG_LEVEL. Safe to call twice."""
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)

    if not any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)

    # uvicorn installs its own plain-text handlers: route its records through ours
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
        if name != "uvicorn" and not any(
            isinstance(f, RedactTokenFilter) for f in uv_logger.filters
        ):
            uv_logger.addFilter(RedactTokenFilter())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
