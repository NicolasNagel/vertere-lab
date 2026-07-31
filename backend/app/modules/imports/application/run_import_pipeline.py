"""Orchestrates every import phase (clinics → veterinarians → veterinarian-clinics backfill →
exam categories → exams → patients) in the dependency order Fase 1-3 requires — vets need
clinics to exist first, the backfill needs both, exams need categories, and none of that
ordering is enforced if a caller invokes the phase endpoints individually in the wrong sequence.

This use case is deliberately phase-list-agnostic about *how* the caller wants the result used:
- **Dry-run**: the router runs this inside a transaction and never commits it — every phase
  still executes for real (so exceptions reflect the actual current DB state, not a guess), but
  nothing persists. Nothing here needs to know that; not calling `uow.commit()` is enough.
- **Commit**: the router commits, then persists every collected exception via
  `ImportExceptionRepository` and marks the batch `COMMITTED` — see `CommitImportUseCase` below.

Both entry points share `_ImportPipelineRunner.run` so the two can never drift on order or skip
a phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamCategoryRepository, ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.imports.application.import_clinics import (
    ImportClinicsCommand,
    ImportClinicsUseCase,
)
from app.modules.imports.application.import_exam_categories import (
    ImportExamCategoriesCommand,
    ImportExamCategoriesUseCase,
)
from app.modules.imports.application.import_exams_from_history import (
    ImportExamsFromHistoryCommand,
    ImportExamsFromHistoryUseCase,
)
from app.modules.imports.application.import_patients import (
    ImportPatientsCommand,
    ImportPatientsUseCase,
)
from app.modules.imports.application.import_veterinarians import (
    ImportVeterinariansCommand,
    ImportVeterinariansUseCase,
)
from app.modules.imports.application.link_veterinarian_clinics_from_history import (
    LinkVeterinarianClinicsFromHistoryCommand,
    LinkVeterinarianClinicsFromHistoryUseCase,
)
from app.modules.imports.domain.entities import ImportException
from app.modules.imports.domain.repositories import (
    ImportBatchRepository,
    ImportExceptionRepository,
    ImportStagingRowRepository,
)
from app.modules.patients.domain.repositories import PatientRepository, SpeciesRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError

_REQUIRED_PERMISSION = "imports.execute"

_PHASE_CLINICS = "clinics"
_PHASE_VETERINARIANS = "veterinarians"
_PHASE_VETERINARIAN_CLINICS_BACKFILL = "veterinarian_clinics_backfill"
_PHASE_EXAM_CATEGORIES = "exam_categories"
_PHASE_EXAMS = "exams"
_PHASE_PATIENTS = "patients"


@dataclass(frozen=True, kw_only=True)
class PipelineException:
    phase: str
    source_row_number: int
    message: str


@dataclass(frozen=True, kw_only=True)
class PipelinePhaseResult:
    phase: str
    imported_count: int
    skipped_existing_count: int
    exceptions: tuple[PipelineException, ...]


@dataclass(frozen=True, kw_only=True)
class ImportPipelineResult:
    batch_id: UUID
    phases: tuple[PipelinePhaseResult, ...]

    @property
    def total_imported_count(self) -> int:
        return sum(phase.imported_count for phase in self.phases)

    @property
    def total_exceptions(self) -> tuple[PipelineException, ...]:
        return tuple(exc for phase in self.phases for exc in phase.exceptions)


class _ImportPipelineRunner:
    """Shared by dry-run and commit — constructs and runs every phase use case against the
    same session-backed repositories, in the fixed dependency order."""

    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        batches: ImportBatchRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        veterinarian_clinic_links: VeterinarianClinicLinkRepository,
        exam_categories: ExamCategoryRepository,
        exams: ExamRepository,
        species: SpeciesRepository,
        patients: PatientRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._staging_rows = staging_rows
        self._batches = batches
        self._clinics = clinics
        self._veterinarians = veterinarians
        self._veterinarian_clinic_links = veterinarian_clinic_links
        self._exam_categories = exam_categories
        self._exams = exams
        self._species = species
        self._patients = patients
        self._audit = audit
        self._clock = clock

    def run(
        self, *, actor_id: UUID | None, actor_permissions: frozenset[str], batch_id: UUID
    ) -> ImportPipelineResult:
        if _REQUIRED_PERMISSION not in actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")
        if self._batches.get_by_id(batch_id) is None:
            raise NotFoundError("Lote de importação não encontrado.")

        phases: list[PipelinePhaseResult] = []

        clinics_result = ImportClinicsUseCase(
            staging_rows=self._staging_rows,
            clinics=self._clinics,
            audit=self._audit,
            clock=self._clock,
        ).execute(
            ImportClinicsCommand(
                actor_id=actor_id, actor_permissions=actor_permissions, batch_id=batch_id
            )
        )
        phases.append(
            PipelinePhaseResult(
                phase=_PHASE_CLINICS,
                imported_count=clinics_result.imported_count,
                skipped_existing_count=clinics_result.skipped_existing_count,
                exceptions=tuple(
                    PipelineException(
                        phase=_PHASE_CLINICS,
                        source_row_number=e.source_row_number,
                        message=e.message,
                    )
                    for e in clinics_result.exceptions
                ),
            )
        )

        vets_result = ImportVeterinariansUseCase(
            staging_rows=self._staging_rows,
            veterinarians=self._veterinarians,
            clinics=self._clinics,
            links=self._veterinarian_clinic_links,
            audit=self._audit,
            clock=self._clock,
        ).execute(
            ImportVeterinariansCommand(
                actor_id=actor_id, actor_permissions=actor_permissions, batch_id=batch_id
            )
        )
        phases.append(
            PipelinePhaseResult(
                phase=_PHASE_VETERINARIANS,
                imported_count=vets_result.imported_count,
                skipped_existing_count=vets_result.skipped_existing_count,
                exceptions=tuple(
                    PipelineException(
                        phase=_PHASE_VETERINARIANS,
                        source_row_number=e.source_row_number,
                        message=e.message,
                    )
                    for e in vets_result.exceptions
                ),
            )
        )

        backfill_result = LinkVeterinarianClinicsFromHistoryUseCase(
            staging_rows=self._staging_rows,
            clinics=self._clinics,
            veterinarians=self._veterinarians,
            links=self._veterinarian_clinic_links,
            audit=self._audit,
            clock=self._clock,
        ).execute(
            LinkVeterinarianClinicsFromHistoryCommand(
                actor_id=actor_id, actor_permissions=actor_permissions, batch_id=batch_id
            )
        )
        phases.append(
            PipelinePhaseResult(
                phase=_PHASE_VETERINARIAN_CLINICS_BACKFILL,
                imported_count=backfill_result.links_created_count,
                skipped_existing_count=0,
                exceptions=tuple(
                    PipelineException(
                        phase=_PHASE_VETERINARIAN_CLINICS_BACKFILL,
                        source_row_number=e.source_row_number,
                        message=e.message,
                    )
                    for e in backfill_result.exceptions
                ),
            )
        )

        categories_result = ImportExamCategoriesUseCase(
            staging_rows=self._staging_rows,
            categories=self._exam_categories,
            audit=self._audit,
            clock=self._clock,
        ).execute(
            ImportExamCategoriesCommand(
                actor_id=actor_id, actor_permissions=actor_permissions, batch_id=batch_id
            )
        )
        phases.append(
            PipelinePhaseResult(
                phase=_PHASE_EXAM_CATEGORIES,
                imported_count=categories_result.imported_count,
                skipped_existing_count=categories_result.skipped_existing_count,
                exceptions=(),
            )
        )

        exams_result = ImportExamsFromHistoryUseCase(
            staging_rows=self._staging_rows,
            exams=self._exams,
            categories=self._exam_categories,
            species=self._species,
            audit=self._audit,
            clock=self._clock,
        ).execute(
            ImportExamsFromHistoryCommand(
                actor_id=actor_id, actor_permissions=actor_permissions, batch_id=batch_id
            )
        )
        phases.append(
            PipelinePhaseResult(
                phase=_PHASE_EXAMS,
                imported_count=exams_result.imported_count,
                skipped_existing_count=exams_result.skipped_existing_count,
                exceptions=tuple(
                    PipelineException(
                        phase=_PHASE_EXAMS, source_row_number=e.source_row_number, message=e.message
                    )
                    for e in exams_result.exceptions
                ),
            )
        )

        patients_result = ImportPatientsUseCase(
            staging_rows=self._staging_rows,
            patients=self._patients,
            species=self._species,
            audit=self._audit,
            clock=self._clock,
        ).execute(
            ImportPatientsCommand(
                actor_id=actor_id, actor_permissions=actor_permissions, batch_id=batch_id
            )
        )
        phases.append(
            PipelinePhaseResult(
                phase=_PHASE_PATIENTS,
                imported_count=patients_result.imported_count,
                skipped_existing_count=patients_result.skipped_existing_count,
                exceptions=tuple(
                    PipelineException(
                        phase=_PHASE_PATIENTS,
                        source_row_number=e.source_row_number,
                        message=e.message,
                    )
                    for e in patients_result.exceptions
                ),
            )
        )

        return ImportPipelineResult(batch_id=batch_id, phases=tuple(phases))


@dataclass(frozen=True, kw_only=True)
class RunImportPipelineCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


class DryRunImportUseCase:
    """Runs every phase for real against the caller's session, but the caller (the router) must
    never commit that transaction — see module docstring. Nothing here persists a durable trace
    of "a dry run happened"; the result only lives in the HTTP response."""

    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        batches: ImportBatchRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        veterinarian_clinic_links: VeterinarianClinicLinkRepository,
        exam_categories: ExamCategoryRepository,
        exams: ExamRepository,
        species: SpeciesRepository,
        patients: PatientRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._runner = _ImportPipelineRunner(
            staging_rows=staging_rows,
            batches=batches,
            clinics=clinics,
            veterinarians=veterinarians,
            veterinarian_clinic_links=veterinarian_clinic_links,
            exam_categories=exam_categories,
            exams=exams,
            species=species,
            patients=patients,
            audit=audit,
            clock=clock,
        )

    def execute(self, command: RunImportPipelineCommand) -> ImportPipelineResult:
        return self._runner.run(
            actor_id=command.actor_id,
            actor_permissions=command.actor_permissions,
            batch_id=command.batch_id,
        )


class CommitImportUseCase:
    """Same phase run as `DryRunImportUseCase`, plus persisting every collected exception and
    marking the batch `COMMITTED` — the caller (the router) commits this transaction.

    Re-running commit on an already-committed batch is idempotent for the actual cadastros
    (each phase use case already guarantees that), but every phase re-derives its exceptions
    from scratch on every run — nothing marks "this row's exception was already reported".
    Without deduplication here, re-committing the same batch N times would insert the same
    `ImportException` row N times, which is exactly the "reprocessar não duplica" rule this
    whole pipeline exists to uphold, just for the exception ledger instead of the business data.
    """

    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        batches: ImportBatchRepository,
        exceptions: ImportExceptionRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        veterinarian_clinic_links: VeterinarianClinicLinkRepository,
        exam_categories: ExamCategoryRepository,
        exams: ExamRepository,
        species: SpeciesRepository,
        patients: PatientRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._runner = _ImportPipelineRunner(
            staging_rows=staging_rows,
            batches=batches,
            clinics=clinics,
            veterinarians=veterinarians,
            veterinarian_clinic_links=veterinarian_clinic_links,
            exam_categories=exam_categories,
            exams=exams,
            species=species,
            patients=patients,
            audit=audit,
            clock=clock,
        )
        self._batches = batches
        self._exceptions = exceptions
        self._clock = clock

    def execute(self, command: RunImportPipelineCommand) -> ImportPipelineResult:
        result = self._runner.run(
            actor_id=command.actor_id,
            actor_permissions=command.actor_permissions,
            batch_id=command.batch_id,
        )

        already_persisted = {
            (exc.phase, exc.source_row_number, exc.message)
            for exc in self._exceptions.list_by_batch(command.batch_id)
        }
        now = self._clock.now()
        exception_rows = [
            ImportException(
                id=uuid4(),
                batch_id=command.batch_id,
                phase=exc.phase,
                source_row_number=exc.source_row_number,
                message=exc.message,
                created_at=now,
            )
            for exc in result.total_exceptions
            if (exc.phase, exc.source_row_number, exc.message) not in already_persisted
        ]
        if exception_rows:
            self._exceptions.add_many(exception_rows)

        batch = self._batches.get_by_id(command.batch_id)
        if batch is None:
            # Unreachable in practice — `_runner.run` above already looked up this same batch
            # and would have raised `NotFoundError` first — but never trust a second lookup.
            raise NotFoundError("Lote de importação não encontrado.")
        batch.mark_committed()
        self._batches.save(batch)

        return result
