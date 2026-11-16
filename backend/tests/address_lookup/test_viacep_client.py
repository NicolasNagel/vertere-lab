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


def _respond(payload: dict[str, object]) -> ViaCepClient:
    return _client(lambda request: httpx.Response(200, json=payload))


def test_lookup_maps_the_payload_and_treats_empty_fields_and_erro_flag_as_missing() -> None:
    address = _respond(
        {
            "cep": "01310-100",
            "logradouro": "Avenida Paulista",
            "bairro": "Bela Vista",
            "localidade": "São Paulo",
            "uf": "SP",
        }
    ).lookup("01310100")
    assert address is not None
    assert (address.street, address.neighborhood, address.city, address.state) == (
        "Avenida Paulista",
        "Bela Vista",
        "São Paulo",
        "SP",
    )

    blank = _respond(
        {"cep": "01310-100", "logradouro": "", "bairro": "", "localidade": "", "uf": ""}
    ).lookup("01310100")
    assert blank is not None
    assert (blank.street, blank.neighborhood) == (None, None)

    assert _respond({"erro": True}).lookup("00000000") is None


def test_lookup_raises_external_service_unavailable_on_timeout_and_server_error() -> None:
    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    with pytest.raises(ExternalServiceUnavailableError):
        _client(time_out).lookup("01310100")
    with pytest.raises(ExternalServiceUnavailableError):
        _client(lambda request: httpx.Response(500, json={})).lookup("01310100")
