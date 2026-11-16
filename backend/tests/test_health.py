from __future__ import annotations

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app


async def test_health_sets_security_headers_keeps_request_id_and_wraps_unknown_routes(
    client: httpx.AsyncClient,
) -> None:
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

    # O X-Request-ID enviado pelo cliente é preservado.
    echoed = await client.get("/api/v1/health", headers={"X-Request-ID": "req-abc-123"})
    assert echoed.headers["X-Request-ID"] == "req-abc-123"

    # Rota inexistente responde com o envelope de erro padrão.
    unknown = await client.get("/api/v1/does-not-exist")
    assert unknown.status_code == 404
    error = unknown.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == unknown.headers["X-Request-ID"]
    assert error["details"] == []


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


async def test_mutations_are_only_accepted_from_trusted_origins(client: httpx.AsyncClient) -> None:
    rejected = await client.post(
        "/api/v1/auth/login", headers={"Origin": "https://attacker.example"}, json={}
    )
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "CSRF_ORIGIN_FORBIDDEN"
    assert rejected.json()["error"]["request_id"] == rejected.headers["X-Request-ID"]

    # Mesma origem chega ao endpoint (404 porque a rota não existe).
    same_origin = await client.post(
        "/api/v1/does-not-exist", headers={"Origin": "http://test"}, json={}
    )
    assert same_origin.status_code == 404

    # Em dev, a origem do Vite também é confiável.
    app = create_app(
        Settings(
            env="dev",
            log_level="WARNING",
            database_url=SecretStr("postgresql+psycopg://test:test@localhost:5499/test_unused"),
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:8200"
    ) as vite_client:
        vite = await vite_client.post(
            "/api/v1/does-not-exist", headers={"Origin": "http://localhost:5173"}, json={}
        )
    assert vite.status_code == 404
