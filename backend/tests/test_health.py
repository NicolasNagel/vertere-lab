from __future__ import annotations

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app


async def test_health_returns_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    assert response.headers["Permissions-Policy"] == "camera=(), geolocation=(), microphone=()"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" not in response.headers


async def test_health_enables_hsts_in_production() -> None:
    app = create_app(
        Settings(
            env="prod",
            log_level="WARNING",
            database_url=SecretStr("postgresql+psycopg://test:test@localhost:5499/test_unused"),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.headers["Strict-Transport-Security"] == ("max-age=31536000; includeSubDomains")


async def test_unknown_route_returns_error_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == response.headers["X-Request-ID"]
    assert error["details"] == []


async def test_request_id_from_client_is_preserved(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "req-abc-123"})

    assert response.headers["X-Request-ID"] == "req-abc-123"


async def test_mutation_from_untrusted_browser_origin_is_rejected(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://attacker.example"},
        json={},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_ORIGIN_FORBIDDEN"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


async def test_mutation_from_same_origin_reaches_the_endpoint(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/does-not-exist",
        headers={"Origin": "http://test"},
        json={},
    )

    assert response.status_code == 404


async def test_mutation_from_trusted_vite_origin_reaches_the_endpoint() -> None:
    app = create_app(
        Settings(
            env="dev",
            log_level="WARNING",
            database_url=SecretStr("postgresql+psycopg://test:test@localhost:5499/test_unused"),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8200"
    ) as client:
        response = await client.post(
            "/api/v1/does-not-exist",
            headers={"Origin": "http://localhost:5173"},
            json={},
        )

    assert response.status_code == 404
