from __future__ import annotations

import httpx
import pytest

from app.modules.address_lookup.infrastructure.viacep_client import ViaCepClient
from app.shared.domain.errors import ExternalServiceUnavailableError


def _client(handler: object) -> ViaCepClient:
    return ViaCepClient(
        base_url="https://viacep.com.br",
        timeout_seconds=3.0,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


def test_maps_via_cep_payload_to_address() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "cep": "01310-100",
                "logradouro": "Avenida Paulista",
                "bairro": "Bela Vista",
                "localidade": "São Paulo",
                "uf": "SP",
            },
        )

    address = _client(handle).lookup("01310100")

    assert address is not None
    assert address.street == "Avenida Paulista"
    assert address.neighborhood == "Bela Vista"
    assert address.city == "São Paulo"
    assert address.state == "SP"


def test_empty_fields_map_to_none() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"cep": "01310-100", "logradouro": "", "bairro": "", "localidade": "", "uf": ""},
        )

    address = _client(handle).lookup("01310100")

    assert address is not None
    assert address.street is None
    assert address.neighborhood is None


def test_provider_erro_flag_returns_none() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"erro": True})

    assert _client(handle).lookup("00000000") is None


def test_timeout_raises_external_service_unavailable() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    with pytest.raises(ExternalServiceUnavailableError):
        _client(handle).lookup("01310100")


def test_server_error_raises_external_service_unavailable() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    with pytest.raises(ExternalServiceUnavailableError):
        _client(handle).lookup("01310100")
