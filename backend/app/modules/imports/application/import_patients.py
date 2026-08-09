"""Derive `Patient` (+ embedded owner fields) from the `Dados` operational
history sheet.

`Patient` carries no clinic reference (`docs/... ADR-004` — Owner has no
entity of its own, and this slice doesn't track which clinic a patient
belongs to either), so the natural dedup key the spreadsheet actually
implies — clinic + owner + patient name — only partially maps onto what the
entity can store. Within a single clinic, repeat visits of the same
(owner, patient) pair are unambiguously the same animal and get merged
(species/sex/breed/age taken from whichever occurrence is most recent and
actually has a value). Across *different* clinics, the same (owner, patient)
pair is genuinely ambiguous — found via analysis of the real spreadsheet:
8 of 1526 distinct pairs recur under a second clinic (e.g. owner "Aline",
patient "Cookie" appears under both "Bicho Urbano" and "Entrepatas"). That
could be the same tutor bringing the same pet through two referral paths,
or two different real animals that happen to share both names. Since the
entity has no field to record which is which, silently merging would risk
conflating two different patients (`.claude/rules/10-data-migration.md` —
"nenhuma deduplicação incerta automática"); silently creating two rows would
duplicate a genuine repeat patient. So: the clinic with the most occurrences
(tie-break: earliest row) is treated as primary and gets the `Patient`; every
other clinic grouping for that same pair becomes an exception for manual
review instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.imports.application.text_normalization import split_owner_name
from app.modules.imports.domain.repositories import ImportStagingRowRepository
from app.modules.patients.domain.entities import Patient, PatientSex, PatientStatus
from app.modules.patients.domain.repositories import PatientRepository, SpeciesRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "imports.execute"

SHEET_NAME = "Dados"
_FIRST_DATA_ROW = 5
_COLUMN_CLINIC = "A"
_COLUMN_DATE = "B"
_COLUMN_PATIENT = "I"
_COLUMN_SPECIES = "J"
_COLUMN_BREED = "K"
_COLUMN_SEX = "L"
_COLUMN_AGE = "M"
_COLUMN_OWNER = "N"

_SEX_BY_LABEL = {
    "macho": PatientSex.MALE,
    "fêmea": PatientSex.FEMALE,
    "femea": PatientSex.FEMALE,
}

_NI_CODES = {"ni", "n/i", "não informado", "nao informado"}
_OWNER_CODE_PATTERN = re.compile(r"\((?P<code>[^()]*)\)\s*$")


def _cell(raw_data: dict[str, object], column: str) -> str | None:
    value = raw_data.get(column)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _date_sort_key(raw_data: dict[str, object]) -> float:
    raw = _cell(raw_data, _COLUMN_DATE)
    if raw is None:
        return -1.0
    try:
        return float(raw)
    except ValueError:
        return -1.0


def _split_owner(raw: str) -> tuple[str, str | None]:
    name = split_owner_name(raw)
    code_match = _OWNER_CODE_PATTERN.search(raw)
    code = code_match.group("code").strip() if code_match else ""
    if not code:
        return name, None
    if code.lower() in _NI_CODES:
        return name, f"Proprietário sem código de cliente registrado na planilha ({code})."
    return name, f"Código de cliente legado da planilha: {code}"


@dataclass(frozen=True, kw_only=True)
class _Occurrence:
    date_key: float
    clinic_display: str
    owner_display: str
    patient_display: str
    species_raw: str | None
    sex_raw: str | None
    breed_raw: str | None
    age_raw: str | None
    owner_note: str | None
    source_row_number: int


@dataclass(frozen=True, kw_only=True)
class ImportPatientsCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class ImportRowException:
    source_row_number: int
    message: str


@dataclass(frozen=True, kw_only=True)
class ImportPatientsResult:
    imported_count: int
    skipped_existing_count: int
    exceptions: tuple[ImportRowException, ...]


@dataclass(frozen=True, kw_only=True)
class _GroupOutcome:
    created: bool
    exception: ImportRowException | None = None


class ImportPatientsUseCase:
    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        patients: PatientRepository,
        species: SpeciesRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._staging_rows = staging_rows
        self._patients = patients
        self._species = species
        self._audit = audit
        self._clock = clock

    def execute(self, command: ImportPatientsCommand) -> ImportPatientsResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        rows = self._staging_rows.list_by_batch(command.batch_id, sheet_name=SHEET_NAME)
        species_ids_by_name = {
            species.name.lower(): species.id for species in self._species.list_all()
        }

        exceptions: list[ImportRowException] = []
        groups: dict[tuple[str, str, str], list[_Occurrence]] = {}

        for row in rows:
            if row.source_row_number < _FIRST_DATA_ROW:
                continue

            patient_name = _cell(row.raw_data, _COLUMN_PATIENT)
            clinic = _cell(row.raw_data, _COLUMN_CLINIC)
            owner_raw = _cell(row.raw_data, _COLUMN_OWNER)
            if patient_name is None:
                continue
            if clinic is None or owner_raw is None:
                exceptions.append(
                    ImportRowException(
                        source_row_number=row.source_row_number,
                        message=(
                            f"Faltam dados de clínica/proprietário para o paciente "
                            f"'{patient_name}'."
                        ),
                    )
                )
                continue

            owner_name, owner_note = _split_owner(owner_raw)
            key = (clinic.lower(), owner_name.lower(), patient_name.lower())
            groups.setdefault(key, []).append(
                _Occurrence(
                    date_key=_date_sort_key(row.raw_data),
                    clinic_display=clinic,
                    owner_display=owner_name,
                    patient_display=patient_name,
                    species_raw=_cell(row.raw_data, _COLUMN_SPECIES),
                    sex_raw=_cell(row.raw_data, _COLUMN_SEX),
                    breed_raw=_cell(row.raw_data, _COLUMN_BREED),
                    age_raw=_cell(row.raw_data, _COLUMN_AGE),
                    owner_note=owner_note,
                    source_row_number=row.source_row_number,
                )
            )

        by_owner_patient: dict[tuple[str, str], dict[str, list[_Occurrence]]] = {}
        for (clinic_l, owner_l, patient_l), occurrences in groups.items():
            by_owner_patient.setdefault((owner_l, patient_l), {})[clinic_l] = occurrences

        imported = 0
        skipped = 0
        now = self._clock.now()

        for clinic_groups in by_owner_patient.values():
            if len(clinic_groups) > 1:
                primary_clinic = max(
                    clinic_groups,
                    key=lambda c: (
                        len(clinic_groups[c]),
                        -min(o.source_row_number for o in clinic_groups[c]),
                    ),
                )
                for clinic_l, occurrences in clinic_groups.items():
                    if clinic_l == primary_clinic:
                        continue
                    first_row = min(occurrences, key=lambda o: o.source_row_number)
                    reason = (
                        f"Paciente '{first_row.patient_display}' do proprietário "
                        f"'{first_row.owner_display}' também aparece na clínica "
                        f"'{first_row.clinic_display}' — mantido apenas na clínica com mais "
                        "ocorrências; revisão manual necessária para confirmar se é o mesmo "
                        "animal."
                    )
                    exceptions.append(
                        ImportRowException(
                            source_row_number=first_row.source_row_number, message=reason
                        )
                    )
                occurrences = clinic_groups[primary_clinic]
            else:
                (occurrences,) = clinic_groups.values()

            outcome = self._process_group(
                occurrences,
                species_ids_by_name=species_ids_by_name,
                actor_id=command.actor_id,
                now=now,
            )
            if outcome.exception is not None:
                exceptions.append(outcome.exception)
            elif outcome.created:
                imported += 1
            else:
                skipped += 1

        return ImportPatientsResult(
            imported_count=imported, skipped_existing_count=skipped, exceptions=tuple(exceptions)
        )

    def _process_group(
        self,
        occurrences: list[_Occurrence],
        *,
        species_ids_by_name: dict[str, UUID],
        actor_id: UUID | None,
        now: datetime,
    ) -> _GroupOutcome:
        ordered = sorted(occurrences, key=lambda o: o.date_key, reverse=True)
        latest = ordered[0]

        owner_name = latest.owner_display
        patient_name = latest.patient_display

        existing = self._patients.get_by_owner_and_name(owner_name=owner_name, name=patient_name)
        if existing is not None:
            return _GroupOutcome(created=False)

        species_occurrence = next((o for o in ordered if o.species_raw), None)
        if species_occurrence is None or species_occurrence.species_raw is None:
            return _GroupOutcome(
                created=False,
                exception=ImportRowException(
                    source_row_number=latest.source_row_number,
                    message=(
                        f"Paciente '{patient_name}' (proprietário '{owner_name}') sem "
                        "espécie informada."
                    ),
                ),
            )
        species_id = species_ids_by_name.get(species_occurrence.species_raw.lower())
        if species_id is None:
            return _GroupOutcome(
                created=False,
                exception=ImportRowException(
                    source_row_number=species_occurrence.source_row_number,
                    message=f"Espécie '{species_occurrence.species_raw}' não encontrada no cadastro.",
                ),
            )

        sex_occurrence = next(
            (o for o in ordered if o.sex_raw and o.sex_raw.lower() in _SEX_BY_LABEL), None
        )
        if sex_occurrence is None or sex_occurrence.sex_raw is None:
            return _GroupOutcome(
                created=False,
                exception=ImportRowException(
                    source_row_number=latest.source_row_number,
                    message=(
                        f"Paciente '{patient_name}' (proprietário '{owner_name}') sem sexo "
                        "informado."
                    ),
                ),
            )
        sex = _SEX_BY_LABEL[sex_occurrence.sex_raw.lower()]

        breed_occurrence = next((o for o in ordered if o.breed_raw), None)
        age_occurrence = next((o for o in ordered if o.age_raw), None)
        note_occurrence = next((o for o in ordered if o.owner_note), None)

        patient = Patient(
            id=uuid4(),
            name=patient_name,
            species_id=species_id,
            sex=sex,
            breed=breed_occurrence.breed_raw if breed_occurrence else None,
            age_description=age_occurrence.age_raw if age_occurrence else None,
            owner_name=owner_name,
            notes=note_occurrence.owner_note if note_occurrence else None,
            status=PatientStatus.ACTIVE,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        self._patients.add(patient)
        self._audit.record(
            AuditEntry(
                actor_user_id=actor_id,
                actor_scope=ActorScope.LAB,
                action="patients.imported",
                entity_type="patient",
                entity_id=str(patient.id),
                after_state={"name": patient.name, "owner_name": patient.owner_name},
            )
        )
        return _GroupOutcome(created=True)
