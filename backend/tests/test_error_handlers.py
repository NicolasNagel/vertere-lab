from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from sqlalchemy.exc import DataError

from app.core.config import Settings
from app.main import create_app
from app.shared.domain.errors import ConflictError


def _app_with_failing_routes(settings: Settings, data_error: DataError | None = None) -> FastAPI:
    app = create_app(settings)
    router = APIRouter(prefix="/api/v1")

    @router.get("/boom-domain")
    def boom_domain() -> None:
        raise ConflictError("Registro em conflito.")

    @router.get("/boom-unexpected")
    def boom_unexpected() -> None:
        raise RuntimeError("segredo interno que nao pode vazar")

    @router.get("/boom-data")
    def boom_data() -> None:
        if data_error is not None:
            raise data_error

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


class _DriverError(Exception):
    def __init__(self, message: str, sqlstate: str | None) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate


def _data_error(sqlstate: str | None) -> DataError:
    return DataError(
        "INSERT ...", {"name": "valor-secreto"}, _DriverError("valor-secreto", sqlstate)
    )


@pytest.mark.parametrize("sqlstate", [None, "22021", "22P05"])
async def test_client_text_data_errors_are_a_422_that_hides_the_value(
    settings: Settings, sqlstate: str | None
) -> None:
    app = _app_with_failing_routes(settings, data_error=_data_error(sqlstate))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/boom-data")

    assert response.status_code == 422
    assert "valor-secreto" not in response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.mark.parametrize("sqlstate", ["22003", "22012", "22007"])
async def test_other_data_errors_stay_a_500_so_a_server_calculation_is_never_blamed_on_the_client(
    settings: Settings, sqlstate: str
) -> None:
    app = _app_with_failing_routes(settings, data_error=_data_error(sqlstate))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    capture = _Capture()
    logger = logging.getLogger("app.errors")
    logger.addHandler(capture)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/boom-data")
    finally:
        logger.removeHandler(capture)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "valor-secreto" not in response.text
    record = next(r for r in capture.records if r.getMessage() == "data_error_not_client_text")
    assert record.__dict__["sqlstate"] == sqlstate
    assert all("valor-secreto" not in r.getMessage() for r in capture.records)


async def test_a_disallowed_method_has_its_own_stable_code(
    failing_client: httpx.AsyncClient,
) -> None:
    response = await failing_client.post("/api/v1/echo-int")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
