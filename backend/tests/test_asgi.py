"""`app/asgi.py` is the Vercel entrypoint (docs/04-arquitetura.md §15) — the
one place that builds the real app from environment-derived settings at
import time, the same way `uvicorn --factory app.main:create_app` does at
process start locally."""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI

from app.core.config import get_settings


def test_asgi_module_exposes_the_app_built_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
    monkeypatch.setenv("ENV", "test")
    get_settings.cache_clear()

    from app import asgi

    try:
        importlib.reload(asgi)

        assert isinstance(asgi.app, FastAPI)
        assert asgi.app.state.settings.env == "test"
    finally:
        get_settings.cache_clear()
