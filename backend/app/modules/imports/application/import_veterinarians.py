"""Normalize + import `Veterinarian` rows from the `Cadastro Veterinários`
staging sheet, linking each to the clinic declared on the same row.

Depends on clinics already being imported into the same batch
(`ImportClinicsUseCase` runs first) — a row whose clinic name isn't found
becomes an exception, never a silently-created clinic (rule:
`.claude/rules/10-data-migration.md` — "nenhuma clínica/veterinário criado
silenciosamente por aproximação incerta").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.imports.domain.entities import ImportRowStatus
from app.modules.imports.domain.repositories import ImportStagingRowRepository
from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.modules.veterinarians.domain.value_objects import Crmv
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "imports.execute"

SHEET_NAME = "Cadastro Veterinários"
_FIRST_DATA_ROW = 3
_STATUS_INACTIVE_VALUES = {"inativo"}
_AUTONOMOUS_CLINIC_NAME = "autonomos"


def _cell(raw_data: dict[str, object], column: str) -> str | None:
    value = raw_data.get(column)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True, kw_only=True)
class ImportVeterinariansCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class ImportRowException:
    source_row_number: int
    message: str


@dataclass(frozen=True, kw_only=True)
class ImportVeterinariansResult:
    imported_count: int
    skipped_existing_count: int
    exceptions: tuple[ImportRowException, ...]


class ImportVeterinariansUseCase:
    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        veterinarians: VeterinarianRepository,
        clinics: ClinicRepository,
        links: VeterinarianClinicLinkRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._staging_rows = staging_rows
        self._veterinarians = veterinarians
        self._clinics = clinics
        self._links = links
        self._audit = audit
        self._clock = clock

    def execute(self, command: ImportVeterinariansCommand) -> ImportVeterinariansResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        rows = self._staging_rows.list_by_batch(command.batch_id, sheet_name=SHEET_NAME)
        clinic_ids_by_name = self._clinics.list_all_names()
        now = self._clock.now()

        imported = 0
        skipped = 0
        exceptions: list[ImportRowException] = []

        for row in rows:
            if row.row_status == ImportRowStatus.IMPORTED:
                continue
            if row.source_row_number < _FIRST_DATA_ROW:
                continue

            clinic_name = _cell(row.raw_data, "A")
            vet_name = _cell(row.raw_data, "B")
            if vet_name is None or clinic_name is None:
                continue

            clinic_id = clinic_ids_by_name.get(clinic_name.lower())
            if clinic_id is None:
                reason = f"Clínica '{clinic_name}' não encontrada no cadastro mestre."
                row.mark_exception(reason)
                self._staging_rows.save(row)
                exceptions.append(
                    ImportRowException(source_row_number=row.source_row_number, message=reason)
                )
                continue

            existing = self._veterinarians.get_by_name(vet_name)
            if existing is not None:
                self._ensure_linked(
                    veterinarian_id=existing.id,
                    clinic_id=clinic_id,
                    actor_id=command.actor_id,
                    now=now,
                    primary=self._links.count_by_veterinarian(existing.id) == 0,
                )
                row.mark_imported()
                self._staging_rows.save(row)
                skipped += 1
                continue

            crmv_raw = _cell(row.raw_data, "C")
            try:
                crmv = Crmv(crmv_raw or "")
            except ValueError as exc:
                row.mark_exception(str(exc))
                self._staging_rows.save(row)
                exceptions.append(
                    ImportRowException(source_row_number=row.source_row_number, message=str(exc))
                )
                continue

            if self._veterinarians.get_by_crmv(str(crmv)) is not None:
                reason = f"CRMV {crmv} já cadastrado para outro veterinário."
                row.mark_exception(reason)
                self._staging_rows.save(row)
                exceptions.append(
                    ImportRowException(source_row_number=row.source_row_number, message=reason)
                )
                continue

            status_raw = (_cell(row.raw_data, "F") or "").lower()
            status = (
                VeterinarianStatus.INACTIVE
                if status_raw in _STATUS_INACTIVE_VALUES
                else VeterinarianStatus.ACTIVE
            )

            veterinarian = Veterinarian(
                id=uuid4(),
                name=vet_name,
                crmv=crmv,
                phone=_cell(row.raw_data, "D"),
                email=_cell(row.raw_data, "E"),
                is_autonomous=clinic_name.strip().lower() == _AUTONOMOUS_CLINIC_NAME,
                status=status,
                notes=_cell(row.raw_data, "G"),
                created_by=command.actor_id,
                updated_by=command.actor_id,
                created_at=now,
                updated_at=now,
            )
            self._veterinarians.add(veterinarian)

            self._audit.record(
                AuditEntry(
                    actor_user_id=command.actor_id,
                    actor_scope=ActorScope.LAB,
                    action="veterinarians.imported",
                    entity_type="veterinarian",
                    entity_id=str(veterinarian.id),
                    after_state={"name": veterinarian.name, "status": veterinarian.status.value},
                )
            )
            self._ensure_linked(
                veterinarian_id=veterinarian.id,
                clinic_id=clinic_id,
                actor_id=command.actor_id,
                now=now,
                primary=True,
            )
            row.mark_imported()
            self._staging_rows.save(row)
            imported += 1

        return ImportVeterinariansResult(
            imported_count=imported, skipped_existing_count=skipped, exceptions=tuple(exceptions)
        )

    def _ensure_linked(
        self,
        *,
        veterinarian_id: UUID,
        clinic_id: UUID,
        actor_id: UUID | None,
        now: datetime,
        primary: bool,
    ) -> None:
        if self._links.get(veterinarian_id, clinic_id) is not None:
            return
        link = VeterinarianClinicLink(
            id=uuid4(),
            veterinarian_id=veterinarian_id,
            clinic_id=clinic_id,
            primary_clinic=primary,
            created_by=actor_id,
            created_at=now,
        )
        self._links.add(link)
        self._audit.record(
            AuditEntry(
                actor_user_id=actor_id,
                actor_scope=ActorScope.LAB,
                action="veterinarian_clinics.linked_from_import",
                entity_type="veterinarian_clinic_link",
                entity_id=str(link.id),
                after_state={
                    "veterinarian_id": str(veterinarian_id),
                    "clinic_id": str(clinic_id),
                    "primary_clinic": str(primary),
                },
            )
        )
