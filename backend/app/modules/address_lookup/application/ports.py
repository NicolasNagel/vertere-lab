"""Port for the CEP lookup provider — implemented in `infrastructure`."""

from __future__ import annotations

from typing import Protocol

from app.modules.address_lookup.domain.entities import CepAddress


class CepLookupPort(Protocol):
    def lookup(self, cep: str) -> CepAddress | None:
        """Return the address for a normalized (8-digit) CEP, or ``None``
        when the provider reports it does not exist."""
        ...
