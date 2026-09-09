from __future__ import annotations

import json
import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import JsonFormatter, request_id_var


def test_missing_database_url_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)

    assert "database_url" in str(excinfo.value)


def test_database_url_never_leaks_in_repr() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:supersecret@host:5432/db",
        _env_file=None,
    )

    assert "supersecret" not in repr(settings)
    assert "supersecret" not in str(settings.database_url)


def test_development_requires_the_vite_browser_origin() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            env="dev",
            database_url="postgresql+psycopg://test:test@localhost/test",
            trusted_browser_origins=("http://127.0.0.1:5173",),
            _env_file=None,
        )

    assert "http://localhost:5173" in str(excinfo.value)


def test_json_formatter_emits_valid_json_with_request_id() -> None:
    token = request_id_var.set("req-log-1")
    try:
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert payload["message"] == "hello world"
    assert payload["request_id"] == "req-log-1"
    assert payload["level"] == "INFO"
