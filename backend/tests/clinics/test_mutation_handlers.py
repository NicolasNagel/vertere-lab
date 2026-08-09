from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import cast

import pytest

from app.modules.clinics.application.create_clinic import CreateClinicCommand
from app.modules.veterinarian_clinics.application import mutation_handlers
from app.modules.veterinarian_clinics.application.uow import ClinicDirectoryUnitOfWork
from tests.identity.fakes import FakeClock


class FakeDirectoryUnitOfWork:
    def __init__(self) -> None:
        repository = object()
        self.clinics = repository
        self.veterinarians = repository
        self.links = repository
        self.audit = repository
        self.commit_count = 0
        self.exit_exception_type: type[BaseException] | None = None

    def __enter__(self) -> FakeDirectoryUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exit_exception_type = exc_type

    def commit(self) -> None:
        self.commit_count += 1


class StubUseCase:
    def __init__(self, result: object) -> None:
        self._result = result

    def execute(self, command: object) -> object:
        return self._result


class FailingUseCase:
    def execute(self, command: object) -> object:
        raise RuntimeError("directory mutation failed")


@pytest.mark.parametrize(
    ("handler_name", "use_case_name", "needs_clock", "returns_result"),
    [
        ("handle_create_clinic", "CreateClinicUseCase", True, True),
        ("handle_update_clinic", "UpdateClinicUseCase", True, True),
        ("handle_deactivate_clinic", "DeactivateClinicUseCase", True, True),
        ("handle_create_veterinarian", "CreateVeterinarianUseCase", True, True),
        ("handle_update_veterinarian", "UpdateVeterinarianUseCase", True, True),
        ("handle_deactivate_veterinarian", "DeactivateVeterinarianUseCase", True, True),
        ("handle_link_veterinarian", "LinkVeterinarianToClinicUseCase", True, False),
        ("handle_unlink_veterinarian", "UnlinkVeterinarianFromClinicUseCase", False, False),
    ],
)
def test_directory_handler_commits_once(
    monkeypatch: pytest.MonkeyPatch,
    handler_name: str,
    use_case_name: str,
    needs_clock: bool,
    returns_result: bool,
) -> None:
    expected = object()
    monkeypatch.setattr(mutation_handlers, use_case_name, lambda **kwargs: StubUseCase(expected))
    uow = FakeDirectoryUnitOfWork()
    kwargs = {"uow": uow, "command": object()}
    if needs_clock:
        kwargs["clock"] = FakeClock(datetime(2026, 8, 9, tzinfo=UTC))

    result = getattr(mutation_handlers, handler_name)(**kwargs)

    assert result is expected if returns_result else result is None
    assert uow.commit_count == 1
    assert uow.exit_exception_type is None


def test_directory_handler_failure_never_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mutation_handlers, "CreateClinicUseCase", lambda **kwargs: FailingUseCase())
    uow = FakeDirectoryUnitOfWork()

    with pytest.raises(RuntimeError, match="directory mutation failed"):
        mutation_handlers.handle_create_clinic(
            uow=cast(ClinicDirectoryUnitOfWork, uow),
            command=cast(CreateClinicCommand, object()),
            clock=FakeClock(datetime(2026, 8, 9, tzinfo=UTC)),
        )

    assert uow.commit_count == 0
    assert uow.exit_exception_type is RuntimeError
