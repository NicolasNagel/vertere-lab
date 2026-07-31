"""Seed `ExamCategory` from the `Suporte` sheet's `Tipo Exame` column — the
hidden dropdown-validation list the spreadsheet itself uses, so the
category vocabulary comes from the source file, not a hardcoded guess.

The catalog starts empty (no migration ever inserted exam/category data),
so this is a fresh seed, not a merge against pre-existing categories beyond
what a previous run of the same batch already created (idempotent by name).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.entities import ExamCategory, ExamCategoryStatus
from app.modules.catalog.domain.repositories import ExamCategoryRepository
from app.modules.imports.domain.repositories import ImportStagingRowRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "imports.execute"

SHEET_NAME = "Suporte"
# Row 1 is blank in the source file (no title row on this hidden sheet,
# unlike the other sheets) — the header ("Tipo Exame", ...) lands on row 2,
# so data starts at row 3.
_FIRST_DATA_ROW = 3
_COLUMN_CATEGORY = "A"


def _cell(raw_data: dict[str, object], column: str) -> str | None:
    value = raw_data.get(column)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True, kw_only=True)
class ImportExamCategoriesCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class ImportExamCategoriesResult:
    imported_count: int
    skipped_existing_count: int


class ImportExamCategoriesUseCase:
    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        categories: ExamCategoryRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._staging_rows = staging_rows
        self._categories = categories
        self._audit = audit
        self._clock = clock

    def execute(self, command: ImportExamCategoriesCommand) -> ImportExamCategoriesResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        rows = self._staging_rows.list_by_batch(command.batch_id, sheet_name=SHEET_NAME)
        now = self._clock.now()

        seen_names: set[str] = set()
        imported = 0
        skipped = 0

        for row in rows:
            if row.source_row_number < _FIRST_DATA_ROW:
                continue

            name = _cell(row.raw_data, _COLUMN_CATEGORY)
            if name is None or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            if self._categories.get_by_name(name) is not None:
                skipped += 1
                continue

            category = ExamCategory(
                id=uuid4(),
                name=name,
                status=ExamCategoryStatus.ACTIVE,
                created_by=command.actor_id,
                updated_by=command.actor_id,
                created_at=now,
                updated_at=now,
            )
            self._categories.add(category)
            self._audit.record(
                AuditEntry(
                    actor_user_id=command.actor_id,
                    actor_scope=ActorScope.LAB,
                    action="exam_categories.imported",
                    entity_type="exam_category",
                    entity_id=str(category.id),
                    after_state={"name": category.name},
                )
            )
            imported += 1

        return ImportExamCategoriesResult(imported_count=imported, skipped_existing_count=skipped)
