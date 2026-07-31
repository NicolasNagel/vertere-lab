"""Backfill `veterinarian_clinics` links implied by the `Dados` operational
history sheet but absent from the `Cadastro Veterinários` master sheet
(e.g. a veterinarian registered only under `Autonomos` who also attended
through a named clinic in the actual history).

Clinic name is resolved case-insensitively against the clinics already
imported — this is the "auto-correct case, review the rest" rule agreed for
this import: a name that differs from the master list only by
case/accent is not fuzzy matching (no edit distance, no approximation), so
it resolves automatically; anything that still doesn't match becomes an
exception, never a silently created clinic. Veterinarian name must match
exactly; the ones that don't (unregistered vets found only in the history)
are always exceptions here — Fase 1 does not create veterinarians from the
`Dados` sheet, only from `Cadastro Veterinários` (`ImportVeterinariansUseCase`).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.imports.domain.repositories import ImportStagingRowRepository
from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "imports.execute"

SHEET_NAME = "Dados"
_FIRST_DATA_ROW = 5
_COLUMN_CLINIC = "A"
_COLUMN_VETERINARIAN = "H"


def _cell(raw_data: dict[str, object], column: str) -> str | None:
    value = raw_data.get(column)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True, kw_only=True)
class LinkVeterinarianClinicsFromHistoryCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class ImportRowException:
    source_row_number: int
    message: str


@dataclass(frozen=True, kw_only=True)
class LinkVeterinarianClinicsFromHistoryResult:
    links_created_count: int
    exceptions: tuple[ImportRowException, ...]


class LinkVeterinarianClinicsFromHistoryUseCase:
    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        links: VeterinarianClinicLinkRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._staging_rows = staging_rows
        self._clinics = clinics
        self._veterinarians = veterinarians
        self._links = links
        self._audit = audit
        self._clock = clock

    def execute(
        self, command: LinkVeterinarianClinicsFromHistoryCommand
    ) -> LinkVeterinarianClinicsFromHistoryResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        rows = self._staging_rows.list_by_batch(command.batch_id, sheet_name=SHEET_NAME)
        clinic_ids_by_name = self._clinics.list_all_names()
        # (vet_id, clinic_id) pairs already linked or created this run, so a
        # history with the same pair on hundreds of rows only does one
        # lookup + one insert instead of one per row.
        seen_pairs: set[tuple[UUID, UUID]] = set()

        created = 0
        exceptions: list[ImportRowException] = []

        for row in rows:
            if row.source_row_number < _FIRST_DATA_ROW:
                continue

            clinic_name = _cell(row.raw_data, _COLUMN_CLINIC)
            vet_name = _cell(row.raw_data, _COLUMN_VETERINARIAN)
            if clinic_name is None or vet_name is None:
                continue

            clinic_id = clinic_ids_by_name.get(clinic_name.lower())
            if clinic_id is None:
                reason = f"Clínica '{clinic_name}' não encontrada no cadastro mestre."
                exceptions.append(
                    ImportRowException(source_row_number=row.source_row_number, message=reason)
                )
                continue

            veterinarian = self._veterinarians.get_by_name(vet_name)
            if veterinarian is None:
                reason = f"Veterinário '{vet_name}' não encontrado no cadastro mestre."
                exceptions.append(
                    ImportRowException(source_row_number=row.source_row_number, message=reason)
                )
                continue

            pair = (veterinarian.id, clinic_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            if self._links.get(veterinarian.id, clinic_id) is not None:
                continue

            now = self._clock.now()
            link = VeterinarianClinicLink(
                id=uuid4(),
                veterinarian_id=veterinarian.id,
                clinic_id=clinic_id,
                primary_clinic=False,
                created_by=command.actor_id,
                created_at=now,
            )
            self._links.add(link)
            self._audit.record(
                AuditEntry(
                    actor_user_id=command.actor_id,
                    actor_scope=ActorScope.LAB,
                    action="veterinarian_clinics.linked_from_import",
                    entity_type="veterinarian_clinic_link",
                    entity_id=str(link.id),
                    after_state={
                        "veterinarian_id": str(veterinarian.id),
                        "clinic_id": str(clinic_id),
                        "primary_clinic": "False",
                        "source": "Dados",
                    },
                )
            )
            created += 1

        return LinkVeterinarianClinicsFromHistoryResult(
            links_created_count=created, exceptions=tuple(exceptions)
        )
