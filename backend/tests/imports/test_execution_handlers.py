from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.modules.imports.application import execution_handlers
from app.modules.imports.application.run_attendance_history_import import (
    RunAttendanceHistoryImportCommand,
)
from app.modules.imports.application.run_price_table_import import RunPriceTableImportCommand
from app.modules.imports.application.uow import ImportUnitOfWork
from tests.imports.fakes import FakeClock


class FakeImportUnitOfWork:
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
        self.exit_exception_type: type[BaseException] | None = None

    def __enter__(self) -> FakeImportUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exit_exception_type = exc_type

    def lock_batch(self, batch_id: UUID) -> None:
        self.locked_batch_id = batch_id

    def commit(self) -> None:
        self.commit_count += 1


class StubUseCase:
    def __init__(self, result: object) -> None:
        self._result = result

    def execute(self, command: object) -> object:
        return self._result


class FailingUseCase:
    def execute(self, command: object) -> object:
        raise RuntimeError("use case failed")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 8, 9, tzinfo=UTC))


@pytest.mark.parametrize(
    ("handler_name", "use_case_name", "command_factory"),
    [
        (
            "handle_dry_run_price_table_import",
            "DryRunPriceTableImportUseCase",
            RunPriceTableImportCommand,
        ),
        (
            "handle_dry_run_attendance_history_import",
            "DryRunAttendanceHistoryImportUseCase",
            RunAttendanceHistoryImportCommand,
        ),
    ],
)
def test_dry_run_locks_batch_without_committing(
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    handler_name: str,
    use_case_name: str,
    command_factory: type[RunPriceTableImportCommand] | type[RunAttendanceHistoryImportCommand],
) -> None:
    expected_result = object()
    monkeypatch.setattr(
        execution_handlers, use_case_name, lambda **kwargs: StubUseCase(expected_result)
    )
    uow = FakeImportUnitOfWork()
    batch_id = uuid4()
    command = command_factory(
        actor_id=uuid4(),
        actor_permissions=frozenset({"imports.execute"}),
        batch_id=batch_id,
    )

    result = getattr(execution_handlers, handler_name)(uow=uow, command=command, clock=clock)

    assert result is expected_result
    assert uow.locked_batch_id == batch_id
    assert uow.commit_count == 0
    assert uow.exit_exception_type is None


@pytest.mark.parametrize(
    ("handler_name", "use_case_name", "command_factory"),
    [
        (
            "handle_commit_price_table_import",
            "CommitPriceTableImportUseCase",
            RunPriceTableImportCommand,
        ),
        (
            "handle_commit_attendance_history_import",
            "CommitAttendanceHistoryImportUseCase",
            RunAttendanceHistoryImportCommand,
        ),
    ],
)
def test_commit_locks_batch_and_commits_once(
    monkeypatch: pytest.MonkeyPatch,
    clock: FakeClock,
    handler_name: str,
    use_case_name: str,
    command_factory: type[RunPriceTableImportCommand] | type[RunAttendanceHistoryImportCommand],
) -> None:
    expected_result = object()
    monkeypatch.setattr(
        execution_handlers, use_case_name, lambda **kwargs: StubUseCase(expected_result)
    )
    uow = FakeImportUnitOfWork()
    batch_id = uuid4()
    command = command_factory(
        actor_id=uuid4(),
        actor_permissions=frozenset({"imports.execute"}),
        batch_id=batch_id,
    )

    result = getattr(execution_handlers, handler_name)(uow=uow, command=command, clock=clock)

    assert result is expected_result
    assert uow.locked_batch_id == batch_id
    assert uow.commit_count == 1
    assert uow.exit_exception_type is None


def test_failure_leaves_commit_unreached(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    monkeypatch.setattr(
        execution_handlers,
        "CommitPriceTableImportUseCase",
        lambda **kwargs: FailingUseCase(),
    )
    uow = FakeImportUnitOfWork()
    batch_id = uuid4()
    command = RunPriceTableImportCommand(
        actor_id=uuid4(),
        actor_permissions=frozenset({"imports.execute"}),
        batch_id=batch_id,
    )

    with pytest.raises(RuntimeError, match="use case failed"):
        execution_handlers.handle_commit_price_table_import(
            uow=cast(ImportUnitOfWork, uow), command=command, clock=clock
        )

    assert uow.locked_batch_id == batch_id
    assert uow.commit_count == 0
    assert uow.exit_exception_type is RuntimeError
