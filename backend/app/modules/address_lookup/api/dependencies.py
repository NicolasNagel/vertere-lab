"""Provider dependency, isolated so tests can override it without a real
network call (rule: .claude/rules/testing.md — mock only at the external
boundary, never the thing under test)."""

from __future__ import annotations

from starlette.requests import Request

from app.modules.address_lookup.application.ports import CepLookupPort
from app.modules.address_lookup.infrastructure.viacep_client import ViaCepClient


def get_cep_lookup_port(request: Request) -> CepLookupPort:
    settings = request.app.state.settings
    return ViaCepClient(
        base_url=settings.viacep_base_url, timeout_seconds=settings.viacep_timeout_seconds
    )
