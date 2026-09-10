"""Vercel entrypoint (docs/04-arquitetura.md §15 — "entrypoint FastAPI único").

Kept separate from `app.main` so `create_app`'s factory stays free of
import-time side effects for tests (see its own docstring) — this module is
the only place that actually builds the app at import time, using settings
read from the real process environment, exactly like a local
`uvicorn --factory app.main:create_app` run does at startup.

Referenced from `backend/pyproject.toml`'s `[tool.vercel] entrypoint`.
"""

from __future__ import annotations

from app.main import create_app

app = create_app()
