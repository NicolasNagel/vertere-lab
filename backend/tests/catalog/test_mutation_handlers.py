from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import cast

import pytest

from app.modules.catalog.application import mutation_handlers
from app.modules.catalog.application.create_exam import CreateExamCommand
from app.modules.catalog.application.uow import CatalogUnitOfWork
from tests.identity.fakes import FakeClock


class FakeCatalogUnitOfWork:
    def __init__(self) -> None:
        repository = object()
        self.exams = repository
        self.categories = repository
        self.species = repository
        self.audit = repository
        self.commit_count = 0
        self.exit_exception_type: type[BaseException] | None = None

    def __enter__(self) -> FakeCatalogUnitOfWork:
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
        raise RuntimeError("catalog mutation failed")


@pytest.mark.parametrize(
    ("handler_name", "use_case_name"),
    [
        ("handle_create_category", "CreateExamCategoryUseCase"),
        ("handle_update_category", "UpdateExamCategoryUseCase"),
        ("handle_deactivate_category", "DeactivateExamCategoryUseCase"),
        ("handle_create_exam", "CreateExamUseCase"),
        ("handle_update_exam", "UpdateExamUseCase"),
        ("handle_deactivate_exam", "DeactivateExamUseCase"),
        ("handle_import_exams", "ImportExamsUseCase"),
    ],
)
def test_catalog_handler_commits_once(
    monkeypatch: pytest.MonkeyPatch, handler_name: str, use_case_name: str
) -> None:
    expected = object()
    monkeypatch.setattr(mutation_handlers, use_case_name, lambda **kwargs: StubUseCase(expected))
    uow = FakeCatalogUnitOfWork()

    result = getattr(mutation_handlers, handler_name)(
        uow=uow,
        command=object(),
        clock=FakeClock(datetime(2026, 8, 9, tzinfo=UTC)),
    )

    assert result is expected
    assert uow.commit_count == 1
    assert uow.exit_exception_type is None


def test_catalog_handler_failure_never_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mutation_handlers, "CreateExamUseCase", lambda **kwargs: FailingUseCase())
    uow = FakeCatalogUnitOfWork()

    with pytest.raises(RuntimeError, match="catalog mutation failed"):
        mutation_handlers.handle_create_exam(
            uow=cast(CatalogUnitOfWork, uow),
            command=cast(CreateExamCommand, object()),
            clock=FakeClock(datetime(2026, 8, 9, tzinfo=UTC)),
        )

    assert uow.commit_count == 0
    assert uow.exit_exception_type is RuntimeError
