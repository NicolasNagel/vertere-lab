"""Normalize + import `Clinic` rows from the `Cadastro Clínicas` staging
sheet.

Reads from `import_staging_rows`, never from the uploaded file directly
(`.claude/rules/10-data-migration.md` — staging is the only source once a
batch exists). One clinic per distinct name; a name that already exists
(from a previous run of the same batch, or created some other way) is
skipped, not duplicated — this is what keeps re-committing a batch
idempotent. A malformed CNPJ/CPF never blocks the row: `TaxId` only accepts
14-digit CNPJ, but several rows in the master sheet carry an 11-digit CPF
(autonomous individuals) or a mistyped document — the raw value is kept in
`notes` instead of being invented into a valid shape or dropped silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.clinics.domain.value_objects import TaxId
from app.modules.imports.domain.entities import ImportRowStatus
from app.modules.imports.domain.repositories import ImportStagingRowRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "imports.execute"

SHEET_NAME = "Cadastro Clínicas"
_FIRST_DATA_ROW = 3
_STATUS_INACTIVE_VALUES = {"inativo"}


def _cell(raw_data: dict[str, object], column: str) -> str | None:
    value = raw_data.get(column)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True, kw_only=True)
class ImportClinicsCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class ImportRowException:
    source_row_number: int
    message: str


@dataclass(frozen=True, kw_only=True)
class ImportClinicsResult:
    imported_count: int
    skipped_existing_count: int
    exceptions: tuple[ImportRowException, ...]


class ImportClinicsUseCase:
    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        clinics: ClinicRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._staging_rows = staging_rows
        self._clinics = clinics
        self._audit = audit
        self._clock = clock

    def execute(self, command: ImportClinicsCommand) -> ImportClinicsResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        rows = self._staging_rows.list_by_batch(command.batch_id, sheet_name=SHEET_NAME)
        known_names = set(self._clinics.list_all_names().keys())
        now = self._clock.now()

        imported = 0
        skipped = 0
        exceptions: list[ImportRowException] = []

        for row in rows:
            if row.row_status == ImportRowStatus.IMPORTED:
                continue
            if row.source_row_number < _FIRST_DATA_ROW:
                continue

            name = _cell(row.raw_data, "A")
            if name is None:
                continue

            if name.lower() in known_names:
                row.mark_imported()
                self._staging_rows.save(row)
                skipped += 1
                continue

            tax_id, tax_id_note = self._resolve_tax_id(_cell(row.raw_data, "B"))
            if tax_id is not None and self._clinics.get_by_tax_id(str(tax_id)) is not None:
                reason = f"CNPJ {tax_id} já cadastrado para outra clínica."
                row.mark_exception(reason)
                self._staging_rows.save(row)
                exceptions.append(
                    ImportRowException(source_row_number=row.source_row_number, message=reason)
                )
                continue

            observation = _cell(row.raw_data, "G")
            notes = " | ".join(part for part in (tax_id_note, observation) if part) or None
            status_raw = (_cell(row.raw_data, "F") or "").lower()
            status = (
                ClinicStatus.INACTIVE
                if status_raw in _STATUS_INACTIVE_VALUES
                else ClinicStatus.ACTIVE
            )

            clinic = Clinic(
                id=uuid4(),
                name=name,
                tax_id=tax_id,
                phone=_cell(row.raw_data, "D"),
                email=_cell(row.raw_data, "E"),
                status=status,
                address_street=_cell(row.raw_data, "C"),
                notes=notes,
                created_by=command.actor_id,
                updated_by=command.actor_id,
                created_at=now,
                updated_at=now,
            )
            self._clinics.add(clinic)
            known_names.add(name.lower())

            self._audit.record(
                AuditEntry(
                    actor_user_id=command.actor_id,
                    actor_scope=ActorScope.LAB,
                    action="clinics.imported",
                    entity_type="clinic",
                    entity_id=str(clinic.id),
                    after_state={"name": clinic.name, "status": clinic.status.value},
                )
            )
            row.mark_imported()
            self._staging_rows.save(row)
            imported += 1

        return ImportClinicsResult(
            imported_count=imported, skipped_existing_count=skipped, exceptions=tuple(exceptions)
        )

    @staticmethod
    def _resolve_tax_id(raw: str | None) -> tuple[TaxId | None, str | None]:
        if raw is None:
            return None, None
        try:
            return TaxId(raw), None
        except ValueError:
            return None, f"Documento da planilha em formato não reconhecido: {raw}"
