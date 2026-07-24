from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.address_lookup.application.ports import CepLookupPort
from app.modules.address_lookup.domain.entities import CepAddress
from app.shared.domain.errors import NotFoundError, ValidationError

_CEP_DIGITS_PATTERN = re.compile(r"^\d{8}$")


@dataclass(frozen=True, kw_only=True)
class LookupCepQuery:
    cep: str


class LookupCepUseCase:
    def __init__(self, *, provider: CepLookupPort) -> None:
        self._provider = provider

    def execute(self, query: LookupCepQuery) -> CepAddress:
        digits = re.sub(r"\D", "", query.cep)
        if not _CEP_DIGITS_PATTERN.match(digits):
            raise ValidationError("CEP inválido. Informe 8 dígitos.")

        address = self._provider.lookup(digits)
        if address is None:
            raise NotFoundError("CEP não encontrado.")

        return address
