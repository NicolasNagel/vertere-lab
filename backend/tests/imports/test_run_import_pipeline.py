from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.imports.application.import_clinics import SHEET_NAME as CLINICS_SHEET
from app.modules.imports.application.import_veterinarians import SHEET_NAME as VETS_SHEET
from app.modules.imports.application.run_import_pipeline import (
    CommitImportUseCase,
    DryRunImportUseCase,
    RunImportPipelineCommand,
)
from app.modules.imports.domain.entities import ImportBatch
from app.modules.patients.domain.entities import Species
from app.shared.domain.errors import ForbiddenError, NotFoundError
from tests.catalog.fakes import FakeExamCategoryRepository, FakeExamRepository
from tests.imports.fakes import (
    FakeClock,
    FakeImportBatchRepository,
    FakeImportExceptionRepository,
    FakeImportStagingRowRepository,
    make_staging_row,
)
from tests.patients.fakes import FakePatientRepository, FakeSpeciesRepository
from tests.veterinarian_clinics.fakes import (
    FakeAuditLogWriter,
    FakeClinicRepository,
    FakeVeterinarianClinicLinkRepository,
    FakeVeterinarianRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_DADOS_SHEET = "Dados"


@dataclass(kw_only=True)
class _Fixture:
    batch_id: UUID
    batches: FakeImportBatchRepository
    staging_rows: FakeImportStagingRowRepository
    clinics: FakeClinicRepository
    veterinarians: FakeVeterinarianRepository
    links: FakeVeterinarianClinicLinkRepository
    categories: FakeExamCategoryRepository
    exams: FakeExamRepository
    species: FakeSpeciesRepository
    patients: FakePatientRepository
    exceptions: FakeImportExceptionRepository

    def dry_run_use_case(self) -> DryRunImportUseCase:
        return DryRunImportUseCase(
            staging_rows=self.staging_rows,
            batches=self.batches,
            clinics=self.clinics,
            veterinarians=self.veterinarians,
            veterinarian_clinic_links=self.links,
            exam_categories=self.categories,
            exams=self.exams,
            species=self.species,
            patients=self.patients,
            audit=FakeAuditLogWriter(),
            clock=FakeClock(_NOW),
        )

    def commit_use_case(self) -> CommitImportUseCase:
        return CommitImportUseCase(
            staging_rows=self.staging_rows,
            batches=self.batches,
            exceptions=self.exceptions,
            clinics=self.clinics,
            veterinarians=self.veterinarians,
            veterinarian_clinic_links=self.links,
            exam_categories=self.categories,
            exams=self.exams,
            species=self.species,
            patients=self.patients,
            audit=FakeAuditLogWriter(),
            clock=FakeClock(_NOW),
        )


def _setup() -> _Fixture:
    batch_id = uuid4()
    batches = FakeImportBatchRepository()
    batches.add(
        ImportBatch(
            id=batch_id, source_filename="planilha.xlsx", checksum_sha256="abc", created_at=_NOW
        )
    )
    staging_rows = FakeImportStagingRowRepository()
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=CLINICS_SHEET,
                source_row_number=3,
                raw_data={"A": "Amizade", "F": "Ativo"},
            ),
            make_staging_row(
                batch_id=batch_id,
                sheet_name=VETS_SHEET,
                source_row_number=3,
                raw_data={"A": "Amizade", "B": "Amanda Pozzi", "C": "11816", "F": "Ativo"},
            ),
            make_staging_row(
                batch_id=batch_id,
                sheet_name="Suporte",
                source_row_number=3,
                raw_data={"A": "Hematológicos"},
            ),
            make_staging_row(
                batch_id=batch_id,
                sheet_name=_DADOS_SHEET,
                source_row_number=5,
                raw_data={
                    "A": "Amizade",
                    "B": "46025",
                    "H": "Amanda Pozzi",
                    "I": "Rex",
                    "J": "Canino",
                    "L": "Macho",
                    "N": "Maria",
                    "O": "Hematológicos",
                    "P": "Hemograma",
                    "R": "25",
                },
            ),
        ]
    )

    return _Fixture(
        batch_id=batch_id,
        batches=batches,
        staging_rows=staging_rows,
        clinics=FakeClinicRepository(),
        veterinarians=FakeVeterinarianRepository(),
        links=FakeVeterinarianClinicLinkRepository(),
        categories=FakeExamCategoryRepository(),
        exams=FakeExamRepository(),
        species=FakeSpeciesRepository([Species(id=uuid4(), name="Canino", created_at=_NOW)]),
        patients=FakePatientRepository(),
        exceptions=FakeImportExceptionRepository(),
    )


_PHASES = [
    "clinics",
    "veterinarians",
    "veterinarian_clinics_backfill",
    "exam_categories",
    "exams",
    "patients",
]


def _command(
    batch_id: UUID, *, permissions: frozenset[str] = frozenset({"imports.execute"})
) -> RunImportPipelineCommand:
    return RunImportPipelineCommand(
        actor_id=uuid4(), actor_permissions=permissions, batch_id=batch_id
    )


def test_pipeline_rejects_missing_permission_and_unknown_batch() -> None:
    fixture = _setup()
    use_case = fixture.dry_run_use_case()

    with pytest.raises(ForbiddenError):
        use_case.execute(_command(fixture.batch_id, permissions=frozenset()))
    with pytest.raises(NotFoundError):
        use_case.execute(_command(uuid4()))


def test_dry_run_executes_every_phase_in_order_and_aggregates_results() -> None:
    fixture = _setup()

    result = fixture.dry_run_use_case().execute(_command(fixture.batch_id))

    assert [phase.phase for phase in result.phases] == _PHASES
    counts = {phase.phase: phase.imported_count for phase in result.phases}
    assert [counts[name] for name in ("clinics", "veterinarians", "exam_categories")] == [1, 1, 1]
    assert (counts["exams"], counts["patients"]) == (1, 1)
    assert result.total_imported_count == sum(counts.values())
    assert result.total_exceptions == ()

    # O caso de uso de dry-run não decide sobre persistência (isso é do router: não comita a
    # transação). Aqui as entidades foram de fato criadas nos fakes, então as exceções refletem
    # estado real, não um palpite.
    assert fixture.clinics.get_by_name("Amizade") is not None


def test_commit_persists_exceptions_once_marks_batch_committed_and_is_idempotent() -> None:
    fixture = _setup()
    # Linha que gera exceção de fase: clínica desconhecida em Dados (fase de vínculo).
    fixture.staging_rows.add_many(
        [
            make_staging_row(
                batch_id=fixture.batch_id,
                sheet_name=_DADOS_SHEET,
                source_row_number=6,
                raw_data={"A": "Clínica Desconhecida", "H": "Amanda Pozzi"},
            )
        ]
    )
    use_case = fixture.commit_use_case()
    command = _command(fixture.batch_id)

    first = use_case.execute(command)
    second = use_case.execute(command)
    use_case.execute(command)

    assert first.total_imported_count > 0
    assert second.total_imported_count == 0  # reimportar o mesmo lote não cria nada
    assert len(first.total_exceptions) >= 1
    # Regressão do QA: cada fase recalcula suas exceções do zero, e recomitar um lote já
    # comitado chegou a inserir a mesma `ImportException` de novo a cada chamada.
    persisted = fixture.exceptions.list_by_batch(fixture.batch_id)
    assert len(persisted) == len(first.total_exceptions)
    assert {p.phase for p in persisted} <= set(_PHASES)

    batch = fixture.batches.get_by_id(fixture.batch_id)
    assert batch is not None
    assert batch.status.value == "COMMITTED"
