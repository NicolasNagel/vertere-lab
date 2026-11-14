"""Structured JSON logging with request correlation.

Stdlib only: a JSON formatter is trivial and the project forbids adding a
dependency for it (.claude/rules/00-global.md).
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class StripQueryFromAccessLog(logging.Filter):
    """Remove a query string do log de acesso do uvicorn.

    Termos de busca (CNPJ, e-mail, telefone, nome de paciente) viajam na query e iriam
    parar no log em claro — `.claude/rules/06-auth-security-lgpd.md`: PII nunca em log.
    O log próprio do app já usa só `request.url.path`.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], args[2].split("?", 1)[0], *args[3:])
        return True


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, StripQueryFromAccessLog) for f in access_logger.filters):
        access_logger.addFilter(StripQueryFromAccessLog())
