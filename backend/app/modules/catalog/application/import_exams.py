"""Bulk-import exams from already-parsed CSV rows.

Two-phase: validate every row first (against current repository state and
duplicates within the same file), then persist only the valid ones in a
single transaction. Invalid rows never touch the session — this is what
keeps "linhas válidas não são interrompidas pelas inválidas" (spec's
acceptance criterion) true without needing per-row rollback.

CSV parsing itself lives in the router (IO belongs there); this use case
only receives structured `ExamImportRow`s (rule: .claude/rules/02-backend.md,
"router só valida protocolo HTTP e delega").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.repositories import ExamCategoryRepository, ExamRepository
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.repositories import SpeciesRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "catalog.manage"


class _RowValidationError(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class ExamImportRow:
    line: int
    code: str
    name: str
    category_name: str
    price_base: str
    description: str | None = None
    species_names: tuple[str, ...] = ()
    active: bool = True


@dataclass(frozen=True, kw_only=True)
class ExamImportRowError:
    line: int
    message: str


@dataclass(frozen=True, kw_only=True)
class ImportExamsCommand:
    actor: AuthenticatedUserDTO
    rows: tuple[ExamImportRow, ...]


@dataclass(frozen=True, kw_only=True)
class ImportExamsResult:
    imported_count: int
    errors: tuple[ExamImportRowError, ...]


class ImportExamsUseCase:
    def __init__(
        self,
        *,
        exams: ExamRepository,
        categories: ExamCategoryRepository,
        species: SpeciesRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._exams = exams
        self._categories = categories
        self._species = species
        self._audit = audit
        self._clock = clock

    def execute(self, command: ImportExamsCommand) -> ImportExamsResult:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        species_by_name = {species.name.lower(): species.id for species in self._species.list_all()}
        now = self._clock.now()

        errors: list[ExamImportRowError] = []
        to_create: list[Exam] = []
        codes_in_file: set[str] = set()

        for row in command.rows:
            try:
                exam = self._build_exam(
                    row,
                    species_by_name=species_by_name,
                    codes_in_file=codes_in_file,
                    now=now,
                    actor_id=command.actor.id,
                )
            except _RowValidationError as exc:
                errors.append(ExamImportRowError(line=row.line, message=str(exc)))
                continue
            codes_in_file.add(str(exam.code))
            to_create.append(exam)

        for exam in to_create:
            self._exams.add(exam)
            self._audit.record(
                AuditEntry(
                    actor_user_id=command.actor.id,
                    actor_scope=ActorScope.LAB,
                    action="exams.imported",
                    entity_type="exam",
                    entity_id=str(exam.id),
                    after_state={"code": str(exam.code), "name": exam.name},
                )
            )

        return ImportExamsResult(imported_count=len(to_create), errors=tuple(errors))

    def _build_exam(
        self,
        row: ExamImportRow,
        *,
        species_by_name: dict[str, UUID],
        codes_in_file: set[str],
        now: datetime,
        actor_id: UUID | None,
    ) -> Exam:
        if not row.name.strip():
            raise _RowValidationError("Nome do exame é obrigatório.")

        category = self._categories.get_by_name(row.category_name)
        if category is None:
            raise _RowValidationError(f"Categoria '{row.category_name}' não encontrada.")

        species_ids: set[UUID] = set()
        for species_name in row.species_names:
            species_id = species_by_name.get(species_name.strip().lower())
            if species_id is None:
                raise _RowValidationError(f"Espécie '{species_name}' não encontrada.")
            species_ids.add(species_id)
        if not species_ids:
            raise _RowValidationError("Informe ao menos uma espécie atendida.")

        try:
            code = ExamCode(row.code)
        except ValueError as exc:
            raise _RowValidationError(str(exc)) from exc

        if str(code) in codes_in_file or self._exams.get_by_code(str(code)) is not None:
            raise _RowValidationError(f"Código '{code}' já cadastrado.")

        try:
            price_base = Decimal(row.price_base)
        except InvalidOperation as exc:
            raise _RowValidationError("Preço base inválido.") from exc

        try:
            return Exam(
                id=uuid4(),
                code=code,
                name=row.name.strip(),
                category_id=category.id,
                price_base=price_base,
                description=row.description,
                species_ids=frozenset(species_ids),
                status=ExamStatus.ACTIVE if row.active else ExamStatus.INACTIVE,
                created_by=actor_id,
                updated_by=actor_id,
                created_at=now,
                updated_at=now,
            )
        except ValueError as exc:
            raise _RowValidationError(str(exc)) from exc
