"""Derive catalog `Exam` entries from the `Dados` (operational history)
sheet's `Exame` column.

Only rows where `Exame` names a **single** exam (no `+`-combined string like
"Check-up 2 + Urinálise") ever get a clean, unambiguous price — a combined
line's total is for the whole bundle, not any one component
(`.claude/rules/10-data-migration.md`: never invent a financial value that
isn't actually recorded). So this use case only reads standalone `Exame`
values; components that appear only inside a `+`-combination are simply
never catalog candidates from this sheet — reconciling those against the
catalog is the historical-attendance import's problem (Fase 4, still
spec-only), not this one's.

Case- and accent-only name variants (`"Hemograma"` vs `"hemograma"`,
`"Básico 3"` vs `"Basico 3"`) are merged into one exam, keyed by a
case+accent-folded name — same "auto-correct case, review the rest" rule
already applied to clinic names in
`link_veterinarian_clinics_from_history.py`, extended to accents because the
real source data has both (found via QA against the actual spreadsheet:
"Basico 3" — a typo missing the accent — and "Básico 3" would otherwise
become two separate catalog rows for the same panel, exactly the
"cadastro sem identificador estável" duplication this project exists to
eliminate). When the same (merged) name occurs on multiple dates with
different prices or categories, the most recent occurrence by date wins for
both — the catalog should reflect the price list currently in effect, not
history.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.repositories import ExamCategoryRepository, ExamRepository
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.imports.application.text_normalization import derive_exam_code, merge_key
from app.modules.imports.domain.repositories import ImportStagingRowRepository
from app.modules.patients.domain.repositories import SpeciesRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.limits import MAX_UNIT_PRICE

_REQUIRED_PERMISSION = "imports.execute"

SHEET_NAME = "Dados"
_FIRST_DATA_ROW = 5
_COLUMN_DATE = "B"
_COLUMN_CATEGORY = "O"
_COLUMN_EXAM = "P"
_COLUMN_PRICE = "R"


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


@dataclass(frozen=True, kw_only=True)
class _ExamOccurrence:
    date_key: float
    name: str
    category_name: str | None
    price: Decimal | None
    source_row_number: int


@dataclass(frozen=True, kw_only=True)
class ImportExamsFromHistoryCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class ImportRowException:
    source_row_number: int
    message: str


@dataclass(frozen=True, kw_only=True)
class ImportExamsFromHistoryResult:
    imported_count: int
    skipped_existing_count: int
    exceptions: tuple[ImportRowException, ...]


class ImportExamsFromHistoryUseCase:
    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        exams: ExamRepository,
        categories: ExamCategoryRepository,
        species: SpeciesRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._staging_rows = staging_rows
        self._exams = exams
        self._categories = categories
        self._species = species
        self._audit = audit
        self._clock = clock

    def execute(self, command: ImportExamsFromHistoryCommand) -> ImportExamsFromHistoryResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        rows = self._staging_rows.list_by_batch(command.batch_id, sheet_name=SHEET_NAME)
        occurrences_by_key: dict[str, list[_ExamOccurrence]] = {}

        for row in rows:
            if row.source_row_number < _FIRST_DATA_ROW:
                continue
            exam_raw = _cell(row.raw_data, _COLUMN_EXAM)
            if exam_raw is None:
                continue
            parts = [part.strip() for part in exam_raw.split("+") if part.strip()]
            if len(parts) != 1:
                continue  # combined line — never a clean standalone price

            name = parts[0]
            price_raw = _cell(row.raw_data, _COLUMN_PRICE)
            try:
                price = Decimal(price_raw) if price_raw else None
            except InvalidOperation:
                price = None
            if price is not None and (not price.is_finite() or price > MAX_UNIT_PRICE):
                price = None  # unreadable / absurd: same as a blank cell, never a crash
            # A zero (or negative) "Valor" shows up on real rows for exams bundled at no extra
            # charge alongside another paid item on the same visit — found via QA against an
            # updated version of the spreadsheet (e.g. "Hematócrito" at 0). `Exam.price_base`
            # requires > 0 (a catalog exam always has a positive base price; "free this time" is
            # a discount at the attendance level, not the exam's price) — treating 0 as "no
            # price" here, same as a blank cell, is what keeps this from crashing the whole
            # import when a zero-priced occurrence would otherwise become the chosen price.
            if price is not None and price <= 0:
                price = None

            occurrence = _ExamOccurrence(
                date_key=_date_sort_key(row.raw_data),
                name=name,
                category_name=_cell(row.raw_data, _COLUMN_CATEGORY),
                price=price,
                source_row_number=row.source_row_number,
            )
            occurrences_by_key.setdefault(merge_key(name), []).append(occurrence)

        species_ids = frozenset(species.id for species in self._species.list_all())
        used_codes: dict[str, str] = {}
        imported = 0
        skipped = 0
        exceptions: list[ImportRowException] = []
        now = self._clock.now()

        for key in sorted(occurrences_by_key):
            occurrences = sorted(occurrences_by_key[key], key=lambda o: o.date_key, reverse=True)
            latest = occurrences[0]
            price = next((o.price for o in occurrences if o.price is not None), None)
            category_name = next((o.category_name for o in occurrences if o.category_name), None)

            code = derive_exam_code(latest.name)
            existing_code_owner = used_codes.get(code)
            if existing_code_owner is not None:
                reason = (
                    f"Código derivado de '{latest.name}' colide com "
                    f"'{existing_code_owner}', já importado nesta rodada."
                )
                exceptions.append(
                    ImportRowException(source_row_number=latest.source_row_number, message=reason)
                )
                continue

            if self._exams.get_by_code(code) is not None:
                skipped += 1
                continue

            if category_name is None:
                reason = f"Exame '{latest.name}' não tem categoria (Tipo de Exame) em nenhuma ocorrência."
                exceptions.append(
                    ImportRowException(source_row_number=latest.source_row_number, message=reason)
                )
                continue
            category = self._categories.get_by_name(category_name)
            if category is None:
                reason = f"Categoria '{category_name}' não encontrada no cadastro."
                exceptions.append(
                    ImportRowException(source_row_number=latest.source_row_number, message=reason)
                )
                continue

            if price is None:
                reason = (
                    f"Exame '{latest.name}' não tem preço numérico válido em nenhuma ocorrência."
                )
                exceptions.append(
                    ImportRowException(source_row_number=latest.source_row_number, message=reason)
                )
                continue

            try:
                exam = Exam(
                    id=uuid4(),
                    code=ExamCode(code),
                    name=latest.name,
                    category_id=category.id,
                    price_base=price,
                    species_ids=species_ids,
                    status=ExamStatus.ACTIVE,
                    created_by=command.actor_id,
                    updated_by=command.actor_id,
                    created_at=now,
                    updated_at=now,
                )
            except ValueError as exc:
                # Last-resort net: any other invariant this entity enforces (present or added
                # later) degrades to a row exception, never an unhandled crash of the whole
                # batch — same "uma linha ruim não trava as demais" rule as everywhere else.
                exceptions.append(
                    ImportRowException(source_row_number=latest.source_row_number, message=str(exc))
                )
                continue
            self._exams.add(exam)
            used_codes[code] = latest.name

            self._audit.record(
                AuditEntry(
                    actor_user_id=command.actor_id,
                    actor_scope=ActorScope.LAB,
                    action="exams.imported_from_history",
                    entity_type="exam",
                    entity_id=str(exam.id),
                    after_state={
                        "code": str(exam.code),
                        "name": exam.name,
                        "price_base": str(exam.price_base),
                    },
                )
            )
            imported += 1

        return ImportExamsFromHistoryResult(
            imported_count=imported, skipped_existing_count=skipped, exceptions=tuple(exceptions)
        )
