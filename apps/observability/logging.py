"""JSON log formatter.

One line of JSON per log record. Stable keys, ISO-8601 timestamps,
``extra`` fields merged into the top-level object so log shippers
can index them without grok rules.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime

_RESERVED_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "asctime",
        "message",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Format ``LogRecord``s as one line of JSON.

    The ``fields`` argument controls which named ``extra`` keys make
    it into the output. Anything else attached as ``extra`` is still
    included, but the named fields are guaranteed present (with a
    ``None`` default) so downstream consumers can rely on the schema.
    """

    def __init__(self, fields: Iterable[str] = ()) -> None:
        super().__init__()
        self._fields = tuple(fields)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for field in self._fields:
            payload.setdefault(field, getattr(record, field, None))

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRS or key in payload:
                continue
            if key.startswith("_"):
                continue
            payload[key] = _safe(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=_safe, ensure_ascii=False)


def _safe(value: object) -> object:
    """Coerce unknown objects into JSON-safe primitives."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list | tuple):
        return [_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    return str(value)
