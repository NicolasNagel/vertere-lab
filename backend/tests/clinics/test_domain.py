from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.clinics.domain.value_objects import TaxId

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_tax_id_normalizes_formatting_punctuation() -> None:
    tax_id = TaxId("78.977.352/0001-99")

    assert str(tax_id) == "78977352000199"


def test_tax_id_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="CNPJ inválido"):
        TaxId("123")


def _clinic(**overrides: object) -> Clinic:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "Clínica Vet",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    defaults.update(overrides)
    return Clinic(**defaults)  # type: ignore[arg-type]


def test_clinic_deactivate_is_idempotent() -> None:
    clinic = _clinic()

    clinic.deactivate(updated_by=None, now=_NOW + timedelta(minutes=1))
    first_updated_at = clinic.updated_at
    clinic.deactivate(updated_by=None, now=_NOW + timedelta(minutes=2))

    assert clinic.status == ClinicStatus.INACTIVE
    assert clinic.updated_at == first_updated_at


def test_clinic_update_details_replaces_all_fields() -> None:
    clinic = _clinic()
    actor = uuid4()

    clinic.update_details(
        name="Novo Nome",
        tax_id=TaxId("78977352000199"),
        phone="(47) 99999-0000",
        email="contato@clinica.com.br",
        status=ClinicStatus.SPECIAL,
        address_zip_code="89255-200",
        address_street="R. Emilio Piazera",
        address_number="80",
        address_neighborhood="Vila Baependi",
        address_city="Jaraguá do Sul",
        address_state="SC",
        address_complement=None,
        notes=None,
        updated_by=actor,
        now=_NOW + timedelta(days=1),
    )

    assert clinic.name == "Novo Nome"
    assert clinic.status == ClinicStatus.SPECIAL
    assert str(clinic.tax_id) == "78977352000199"
    assert clinic.updated_by == actor
