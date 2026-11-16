"""Pydantic schemas for the clinics API — create/update/read/filter kept
separate; never the SQLAlchemy model (rule: .claude/rules/02-backend.md)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.modules.clinics.domain.value_objects import TaxId

ClinicStatusLiteral = Literal["ACTIVE", "INACTIVE", "DELINQUENT", "SPECIAL"]


def _valid_tax_id(value: str) -> str:
    TaxId(value)
    return value


ClinicTaxId = Annotated[str, AfterValidator(_valid_tax_id)]


def _zip_digits(value: str) -> str:
    # A tela envia o CEP mascarado (12345-678); a coluna guarda só os 8 dígitos.
    digits = re.sub(r"\D", "", value)
    if len(digits) != 8:
        raise ValueError("CEP deve ter 8 dígitos.")
    return digits


# Limites explícitos: sem eles um texto gigante vira 500 (índice/coluna) ou lixo no banco.
ClinicName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ClinicPhone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
ClinicEmail = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]
ClinicZipCode = Annotated[str, StringConstraints(max_length=20), AfterValidator(_zip_digits)]
ClinicAddressLine = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
ClinicAddressShort = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]
ClinicNotes = Annotated[str, StringConstraints(max_length=2000)]


class ClinicRead(BaseModel):
    id: UUID
    name: str
    tax_id: str | None
    phone: str | None
    email: str | None
    status: ClinicStatusLiteral
    address_zip_code: str | None
    address_street: str | None
    address_number: str | None
    address_neighborhood: str | None
    address_city: str | None
    address_state: str | None
    address_complement: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    row_version: int


class ClinicListResponse(BaseModel):
    items: list[ClinicRead]
    total: int
    page: int
    page_size: int


class ClinicLinkedVeterinarian(BaseModel):
    veterinarian_id: UUID
    veterinarian_name: str
    crmv: str
    primary_clinic: bool


class ClinicDetailRead(ClinicRead):
    veterinarians: list[ClinicLinkedVeterinarian]


class ClinicCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ClinicName
    tax_id: ClinicTaxId | None = None
    phone: ClinicPhone | None = None
    email: ClinicEmail | None = None
    address_zip_code: ClinicZipCode | None = None
    address_street: ClinicAddressLine | None = None
    address_number: ClinicAddressShort | None = None
    address_neighborhood: ClinicAddressLine | None = None
    address_city: ClinicAddressLine | None = None
    address_state: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    address_complement: ClinicAddressLine | None = None
    notes: ClinicNotes | None = None


class ClinicUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ClinicName
    tax_id: ClinicTaxId | None = None
    phone: ClinicPhone | None = None
    email: ClinicEmail | None = None
    status: ClinicStatusLiteral
    address_zip_code: ClinicZipCode | None = None
    address_street: ClinicAddressLine | None = None
    address_number: ClinicAddressShort | None = None
    address_neighborhood: ClinicAddressLine | None = None
    address_city: ClinicAddressLine | None = None
    address_state: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    address_complement: ClinicAddressLine | None = None
    notes: ClinicNotes | None = None
    expected_row_version: int
