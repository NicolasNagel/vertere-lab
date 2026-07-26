"""Unit test for the global error envelope — isolated from any real route
or database, since `IntegrityError` has no natural reachable path through
the API once every use case pre-checks its FKs (species/category are
validated before persisting). This test exercises the handler directly by
mounting a throwaway route that raises the exception."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.error_handlers import register_error_handlers


def _build_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise IntegrityError(
            "INSERT INTO exams (code) VALUES (%s)",
            {"code": "HEM001"},
            Exception("duplicate key value violates unique constraint"),
        )

    return app


def test_integrity_error_maps_to_409_without_leaking_details() -> None:
    client = TestClient(_build_app(), raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "CONFLICT"
    # Never leak table/column/constraint names or the raw SQL to the client
    # (rule: .claude/rules/globals.md, "erro não expõe detalhe interno").
    assert "exams" not in body["error"]["message"]
    assert "constraint" not in body["error"]["message"]
