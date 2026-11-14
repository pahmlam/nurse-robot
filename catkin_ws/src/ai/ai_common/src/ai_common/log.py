"""JSON line logging for AI modules.

Each record: ``{"ts", "level", "module", "event", "data"?, "exc"?}``. Do not put user utterances
or patient data in ``data`` at INFO level (spec/docs/convention.md §5).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TextIO, Union

LOGGER_NAMESPACE = "ai"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        module = record.name
        if module.startswith(LOGGER_NAMESPACE + "."):
            module = module[len(LOGGER_NAMESPACE) + 1 :]
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": module,
            "event": getattr(record, "event", None) or record.getMessage(),
        }
        data = getattr(record, "data", None)
        if data:
            payload["data"] = data
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def get_logger(
    module: str, level: Union[str, int] = "INFO", stream: Optional[TextIO] = None
) -> logging.Logger:
    """Logger ``ai.<module>`` writing JSON lines. Safe to call repeatedly (one handler)."""
    logger = logging.getLogger(f"{LOGGER_NAMESPACE}.{module}")
    if not logger.handlers:
        handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    level: int = logging.INFO,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    """Log a named event with structured fields."""
    logger.log(level, event, extra={"event": event, "data": fields}, exc_info=exc_info)
