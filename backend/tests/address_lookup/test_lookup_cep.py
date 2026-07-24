from __future__ import annotations

import pytest

from app.modules.address_lookup.application.lookup_cep import LookupCepQuery, LookupCepUseCase
from app.modules.address_lookup.application.ports import CepLookupPort
from app.modules.address_lookup.domain.entities import CepAddress
from app.shared.domain.errors import NotFoundError, ValidationError


class _FakePort(CepLookupPort):
    def __init__(self, *, result: CepAddress | None) -> None:
        self.result = result
        self.received_cep: str | None = None

    def lookup(self, cep: str) -> CepAddress | None:
        self.received_cep = cep
        return self.result


def test_normalizes_masked_cep_before_calling_provider() -> None:
    address = CepAddress(
        zip_code="01310100",
        street="Av. Paulista",
        neighborhood="Bela Vista",
        city="São Paulo",
        state="SP",
    )
    port = _FakePort(result=address)
    use_case = LookupCepUseCase(provider=port)

    result = use_case.execute(LookupCepQuery(cep="01310-100"))

    assert port.received_cep == "01310100"
    assert result == address


def test_malformed_cep_raises_validation_error_without_calling_provider() -> None:
    port = _FakePort(result=None)
    use_case = LookupCepUseCase(provider=port)

    with pytest.raises(ValidationError):
        use_case.execute(LookupCepQuery(cep="123"))

    assert port.received_cep is None


def test_provider_returning_none_raises_not_found() -> None:
    port = _FakePort(result=None)
    use_case = LookupCepUseCase(provider=port)

    with pytest.raises(NotFoundError):
        use_case.execute(LookupCepQuery(cep="00000000"))
