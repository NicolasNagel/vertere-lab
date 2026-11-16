"""Patients domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/00-global.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.

`Owner` has no entity/module of its own: per explicit product decision
(`/planejar-fatia` for this slice — no dedicated Owners screen, "Owner é só
mais uma informação do paciente"), owner data lives as plain fields on
`Patient` (`owner_name`, `owner_phone`, `owner_document`), not as a separate
referenced aggregate. This diverges from the `OWNER --> PATIENT` edge in
`docs/03-modelo-de-dominio.md`'s dependency graph — documented as a
deliberate simplification for this slice, not an oversight, since `Owner`
is never selected/managed independently anywhere in the current UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from app.shared.domain.errors import ValidationError


@dataclass(frozen=True, kw_only=True)
class Species:
    id: UUID
    name: str
    created_at: datetime


class PatientSex(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class PatientStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AgeUnit(StrEnum):
    YEARS = "YEARS"
    MONTHS = "MONTHS"


_MAX_AGE_BY_UNIT = {AgeUnit.YEARS: 120, AgeUnit.MONTHS: 1440}


@dataclass(frozen=True)
class PatientAge:
    """Idade informada do animal: número + unidade (anos ou meses).

    Animal com menos de 1 ano é informado em meses. Fica estruturada (e não só texto) porque
    laudos e relatórios dependem dela; a data em que foi informada fica no `Patient`.
    """

    value: int
    unit: AgeUnit

    def __post_init__(self) -> None:
        if self.value < 0 or self.value > _MAX_AGE_BY_UNIT[self.unit]:
            raise ValidationError(
                f"Idade fora do intervalo permitido para {self.unit.value}: {self.value}."
            )

    @classmethod
    def from_optional(cls, value: int | None, unit: str | None) -> PatientAge | None:
        if value is None and unit is None:
            return None
        if value is None or unit is None:
            raise ValidationError("Informe o valor e a unidade da idade (anos ou meses).")
        try:
            return cls(value=value, unit=AgeUnit(unit))
        except ValueError as exc:
            raise ValidationError(f"Unidade de idade inválida: {unit}.") from exc

    def describe(self) -> str:
        if self.unit is AgeUnit.YEARS:
            return "1 ano" if self.value == 1 else f"{self.value} anos"
        return "1 mês" if self.value == 1 else f"{self.value} meses"


@dataclass(kw_only=True)
class Patient:
    id: UUID
    clinic_id: UUID | None = None
    name: str
    species_id: UUID
    sex: PatientSex
    breed: str | None = None
    age_description: str | None = None
    age: PatientAge | None = None
    age_recorded_on: date | None = None
    owner_name: str
    owner_phone: str | None = None
    owner_document: str | None = None
    status: PatientStatus = PatientStatus.ACTIVE
    notes: str | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1

    def update_details(
        self,
        *,
        name: str,
        species_id: UUID,
        sex: PatientSex,
        breed: str | None,
        age_description: str | None,
        age: PatientAge | None,
        owner_name: str,
        owner_phone: str | None,
        owner_document: str | None,
        status: PatientStatus,
        notes: str | None,
        clinic_id: UUID | None,
        updated_by: UUID | None,
        now: datetime,
    ) -> None:
        self.name = name
        self.species_id = species_id
        self.sex = sex
        self.breed = breed
        self.age_description = age_description
        self.change_age(age, today=now.date())
        self.owner_name = owner_name
        self.owner_phone = owner_phone
        self.owner_document = owner_document
        self.status = status
        self.notes = notes
        self.clinic_id = clinic_id
        self.updated_by = updated_by
        self.updated_at = now

    def change_age(self, age: PatientAge | None, *, today: date) -> None:
        """Atualiza a idade estruturada. A data de registro só muda quando a idade muda.
        Com idade estruturada, `age_description` passa a ser derivada dela."""
        if age is None:
            self.age = None
            self.age_recorded_on = None
            return
        if age != self.age or self.age_recorded_on is None:
            self.age_recorded_on = today
        self.age = age
        self.age_description = age.describe()

    def deactivate(self, *, updated_by: UUID | None, now: datetime) -> None:
        if self.status == PatientStatus.INACTIVE:
            return
        self.status = PatientStatus.INACTIVE
        self.updated_by = updated_by
        self.updated_at = now
