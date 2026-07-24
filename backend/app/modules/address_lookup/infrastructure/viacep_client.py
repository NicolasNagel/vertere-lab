"""ViaCEP adapter — the only provider for CEP lookup today.

One adapter per provider, explicit timeout, no retry (rule:
.claude/rules/integrations-fields.md). A new client instance per call is
deliberate: call volume here is one lookup per form fill, so a persistent
pool is an optimization with no measured need yet (rule: performance —
"meça antes de otimizar").
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from app.modules.address_lookup.application.ports import CepLookupPort
from app.modules.address_lookup.domain.entities import CepAddress
from app.shared.domain.errors import ExternalServiceUnavailableError

logger = logging.getLogger("app.address_lookup")


class _ViaCepPayload(BaseModel):
    erro: bool = False
    cep: str = ""
    logradouro: str = ""
    bairro: str = ""
    localidade: str = ""
    uf: str = ""


class ViaCepClient(CepLookupPort):
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """``transport`` is only ever overridden by tests (``httpx.MockTransport``)
        so they can control the HTTP layer without a real network call."""
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def lookup(self, cep: str) -> CepAddress | None:
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout_seconds),
                transport=self._transport,
            ) as client:
                response = client.get(f"/ws/{cep}/json/")
                response.raise_for_status()
                payload = _ViaCepPayload.model_validate(response.json())
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("viacep lookup failed", extra={"error": str(exc)})
            raise ExternalServiceUnavailableError(
                "Serviço de consulta de CEP indisponível. Preencha o endereço manualmente."
            ) from exc

        if payload.erro:
            return None

        return CepAddress(
            zip_code=cep,
            street=payload.logradouro or None,
            neighborhood=payload.bairro or None,
            city=payload.localidade or None,
            state=payload.uf or None,
        )
