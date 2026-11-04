import json
import logging
import sys
from datetime import UTC, datetime

_SKIPPED_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message", "asctime", "color_message",  # color_message: uvicorn's duplicate with ANSI codes
}


class JsonFormatter(logging.Formatter):
    """One JSON object per line: ts, level, logger, message (+ exc_info, extras)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in vars(record).items():
            if key not in _SKIPPED_ATTRS:
                payload[key] = value
        return json.dumps(payload, default=str)


def setup_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("docker").setLevel(logging.WARNING)
