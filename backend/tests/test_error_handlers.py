from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import APIRouter, FastAPI

from app.core.config import Settings
from app.main import create_app
from app.shared.domain.errors import ConflictError


def _app_with_failing_routes(settings: Settings) -> FastAPI:
    app = create_app(settings)
    router = APIRouter(prefix="/api/v1")

    @router.get("/boom-domain")
    def boom_domain() -> None:
        raise ConflictError("Registro em conflito.")

    @router.get("/boom-unexpected")
    def boom_unexpected() -> None:
        raise RuntimeError("segredo interno que nao pode vazar")

    @router.get("/echo-int")
    def echo_int(value: int) -> dict[str, int]:
        return {"value": value}

    app.include_router(router)
    return app


@pytest.fixture
async def failing_client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    # raise_app_exceptions=False: queremos observar a resposta 500 que o
    # cliente real receberia, não a exceção re-levantada pelo transporte.
    transport = httpx.ASGITransport(
        app=_app_with_failing_routes(settings), raise_app_exceptions=False
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def test_domain_error_maps_to_stable_code_and_status(
    failing_client: httpx.AsyncClient,
) -> None:
    response = await failing_client.get("/api/v1/boom-domain")

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["message"] == "Registro em conflito."
    assert error["request_id"]


async def test_unexpected_error_hides_internals(failing_client: httpx.AsyncClient) -> None:
    response = await failing_client.get("/api/v1/boom-unexpected")

    assert response.status_code == 500
    body = response.text
    assert "segredo interno" not in body
    assert "Traceback" not in body
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"


async def test_request_validation_error_lists_fields(failing_client: httpx.AsyncClient) -> None:
    response = await failing_client.get("/api/v1/echo-int", params={"value": "not-a-number"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any("value" in detail["field"] for detail in error["details"])
