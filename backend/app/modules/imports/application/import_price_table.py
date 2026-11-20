"""Apply the staged price-table PDF onto the existing exam catalog.

This only ever **updates** `Exam.price_base` on an exam that already exists —
it never creates a new `Exam` from a PDF row, even when the name doesn't
match anything (`.claude/rules/10-data-migration.md`: "nenhum merge incerto
automático"; confirmed with the team that a PDF-only name should route to
review, not become a guessed-at new catalog entry). Two of the spreadsheet's
seven exam categories (Tercerizados, Dermatológicos) never appear in this
PDF at all — those exams simply never match a PDF row and keep whatever
price Fase 2 (the spreadsheet-derived import) gave them; that's the intended
outcome, not a gap to report.

Matching is case+accent-folded (`text_normalization.merge_key`, shared with
`import_exams_from_history.py`) since the PDF's spelling of an exam name and
the catalog's spelling — itself derived from the spreadsheet — are two
independent sources that won't always agree on capitalization or accents.

Same price, no-op: counted as `skipped_existing_count`, not re-audited —
Fase 2b is expected to be re-run every time the clinic updates its price
list, and a same-price re-run shouldn't spam the audit log.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.imports.application.stage_price_table_pdf import SHEET_NAME
from app.modules.imports.application.text_normalization import merge_key
from app.modules.imports.domain.repositories import ImportStagingRowRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.limits import MAX_UNIT_PRICE

_REQUIRED_PERMISSION = "imports.execute"


@dataclass(frozen=True, kw_only=True)
class ImportPriceTableCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class ImportRowException:
    source_row_number: int
    message: str


@dataclass(frozen=True, kw_only=True)
class ImportPriceTableResult:
    imported_count: int
    skipped_existing_count: int
    exceptions: tuple[ImportRowException, ...]


class ImportPriceTableUseCase:
    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._staging_rows = staging_rows
        self._exams = exams
        self._audit = audit
        self._clock = clock

    def execute(self, command: ImportPriceTableCommand) -> ImportPriceTableResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        rows = self._staging_rows.list_by_batch(command.batch_id, sheet_name=SHEET_NAME)
        exam_ids_by_key = {
            merge_key(name): id_ for name, id_ in self._exams.list_all_names().items()
        }

        updated = 0
        skipped = 0
        exceptions: list[ImportRowException] = []
        now = self._clock.now()

        for row in rows:
            name = row.raw_data.get("name")
            price_raw = row.raw_data.get("price")
            category = row.raw_data.get("category") or ""
            if not isinstance(name, str) or not isinstance(price_raw, str):
                exceptions.append(
                    ImportRowException(
                        source_row_number=row.source_row_number,
                        message="Linha de preço sem nome ou valor legível.",
                    )
                )
                continue

            try:
                price = Decimal(price_raw)
            except InvalidOperation:
                exceptions.append(
                    ImportRowException(
                        source_row_number=row.source_row_number,
                        message=f"Preço '{price_raw}' do exame '{name}' não é um valor numérico válido.",
                    )
                )
                continue

            if not price.is_finite() or price > MAX_UNIT_PRICE:
                exceptions.append(
                    ImportRowException(
                        source_row_number=row.source_row_number,
                        message=(
                            f"Preço '{price_raw}' do exame '{name}' está fora do limite "
                            f"(até R$ {MAX_UNIT_PRICE})."
                        ),
                    )
                )
                continue

            exam_id = exam_ids_by_key.get(merge_key(name))
            if exam_id is None:
                exceptions.append(
                    ImportRowException(
                        source_row_number=row.source_row_number,
                        message=(
                            f"Exame '{name}' do PDF (categoria '{category}') não encontrado no "
                            "catálogo — mantém o preço atual, se existir."
                        ),
                    )
                )
                continue

            exam = self._exams.get_by_id(exam_id)
            if exam is None:
                # Repository returned this id from list_all_names() a moment ago — treat a
                # since-deleted row as a review case, never a crash.
                exceptions.append(
                    ImportRowException(
                        source_row_number=row.source_row_number,
                        message=f"Exame '{name}' não encontrado ao tentar atualizar o preço.",
                    )
                )
                continue

            if exam.price_base == price:
                skipped += 1
                continue

            before_price = str(exam.price_base)
            exam.update_price_base(price_base=price, updated_by=command.actor_id, now=now)
            self._exams.save(exam)
            self._audit.record(
                AuditEntry(
                    actor_user_id=command.actor_id,
                    actor_scope=ActorScope.LAB,
                    action="exams.price_updated_from_price_table",
                    entity_type="exam",
                    entity_id=str(exam.id),
                    before_state={"price_base": before_price},
                    after_state={"price_base": str(exam.price_base)},
                )
            )
            updated += 1

        return ImportPriceTableResult(
            imported_count=updated, skipped_existing_count=skipped, exceptions=tuple(exceptions)
        )
