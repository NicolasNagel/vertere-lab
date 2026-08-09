from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from app.modules.imports.application import pipeline_handlers
from app.modules.imports.application.import_clinics import ImportClinicsCommand
from app.modules.imports.application.import_exam_categories import ImportExamCategoriesCommand
from app.modules.imports.application.import_exams_from_history import ImportExamsFromHistoryCommand
from app.modules.imports.application.import_patients import ImportPatientsCommand
from app.modules.imports.application.import_veterinarians import ImportVeterinariansCommand
from app.modules.imports.application.link_veterinarian_clinics_from_history import (
    LinkVeterinarianClinicsFromHistoryCommand,
)
from app.modules.imports.application.run_import_pipeline import RunImportPipelineCommand
from tests.imports.fakes import FakeClock


class FakePipelineUnitOfWork:
    def __init__(self) -> None:
        repository = object()
        self.batches = repository
        self.staging_rows = repository
        self.exceptions = repository
        self.exams = repository
        self.exam_categories = repository
        self.attendances = repository
        self.attendance_sequences = repository
        self.clinics = repository
        self.veterinarians = repository
        self.patients = repository
        self.species = repository
        self.veterinarian_clinic_links = repository
        self.audit = repository
        self.locked_batch_id: UUID | None = None
        self.commit_count = 0

    def __enter__(self) -> FakePipelineUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def lock_batch(self, batch_id: UUID) -> None:
        self.locked_batch_id = batch_id

    def commit(self) -> None:
        self.commit_count += 1


class StubUseCase:
    def __init__(self, result: object) -> None:
        self._result = result

    def execute(self, command: object) -> object:
        return self._result


@pytest.mark.parametrize(
    ("handler_name", "use_case_name", "command_factory"),
    [
        ("handle_import_clinics", "ImportClinicsUseCase", ImportClinicsCommand),
        (
            "handle_import_veterinarians",
            "ImportVeterinariansUseCase",
            ImportVeterinariansCommand,
        ),
        (
            "handle_link_veterinarian_clinics",
            "LinkVeterinarianClinicsFromHistoryUseCase",
            LinkVeterinarianClinicsFromHistoryCommand,
        ),
        (
            "handle_import_exam_categories",
            "ImportExamCategoriesUseCase",
            ImportExamCategoriesCommand,
        ),
        ("handle_import_exams", "ImportExamsFromHistoryUseCase", ImportExamsFromHistoryCommand),
        ("handle_import_patients", "ImportPatientsUseCase", ImportPatientsCommand),
    ],
)
def test_phase_handlers_lock_and_commit_once(
    monkeypatch: pytest.MonkeyPatch,
    handler_name: str,
    use_case_name: str,
    command_factory: type,
) -> None:
    expected_result = object()
    monkeypatch.setattr(
        pipeline_handlers, use_case_name, lambda **kwargs: StubUseCase(expected_result)
    )
    uow = FakePipelineUnitOfWork()
    batch_id = uuid4()
    command = command_factory(
        actor_id=uuid4(),
        actor_permissions=frozenset({"imports.execute"}),
        batch_id=batch_id,
    )

    result = getattr(pipeline_handlers, handler_name)(
        uow=uow, command=command, clock=FakeClock(datetime(2026, 8, 9, tzinfo=UTC))
    )

    assert result is expected_result
    assert uow.locked_batch_id == batch_id
    assert uow.commit_count == 1


@pytest.mark.parametrize(
    ("handler_name", "use_case_name", "expected_commits"),
    [
        ("handle_dry_run_import_pipeline", "DryRunImportUseCase", 0),
        ("handle_commit_import_pipeline", "CommitImportUseCase", 1),
    ],
)
def test_pipeline_handler_owns_transaction_outcome(
    monkeypatch: pytest.MonkeyPatch,
    handler_name: str,
    use_case_name: str,
    expected_commits: int,
) -> None:
    expected_result = object()
    monkeypatch.setattr(
        pipeline_handlers, use_case_name, lambda **kwargs: StubUseCase(expected_result)
    )
    uow = FakePipelineUnitOfWork()
    batch_id = uuid4()
    command = RunImportPipelineCommand(
        actor_id=uuid4(),
        actor_permissions=frozenset({"imports.execute"}),
        batch_id=batch_id,
    )

    result = getattr(pipeline_handlers, handler_name)(
        uow=uow, command=command, clock=FakeClock(datetime(2026, 8, 9, tzinfo=UTC))
    )

    assert result is expected_result
    assert uow.locked_batch_id == batch_id
    assert uow.commit_count == expected_commits
