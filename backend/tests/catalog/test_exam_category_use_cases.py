from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.catalog.application.create_exam_category import (
    CreateExamCategoryCommand,
    CreateExamCategoryUseCase,
)
from app.modules.catalog.application.deactivate_exam_category import (
    DeactivateExamCategoryCommand,
    DeactivateExamCategoryUseCase,
)
from app.modules.catalog.application.get_exam_category import (
    GetExamCategoryQuery,
    GetExamCategoryUseCase,
)
from app.modules.catalog.application.list_exam_categories import (
    ListExamCategoriesQuery,
    ListExamCategoriesUseCase,
)
from app.modules.catalog.application.update_exam_category import (
    UpdateExamCategoryCommand,
    UpdateExamCategoryUseCase,
)
from app.modules.catalog.domain.entities import ExamCategoryStatus
from app.modules.catalog.domain.errors import DuplicateExamCategoryNameError
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError
from tests.catalog.fakes import FakeAuditLogWriter, FakeClock, FakeExamCategoryRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        id=uuid4(),
        email="user@vertere.local",
        full_name="User",
        role_id=uuid4(),
        role_name="FINANCE",
        permissions=permissions,
    )


def _create_command(**overrides: object) -> CreateExamCategoryCommand:
    defaults: dict[str, object] = {
        "actor": _actor(permissions=frozenset({"catalog.manage"})),
        "name": "Hematologia",
    }
    defaults.update(overrides)
    return CreateExamCategoryCommand(**defaults)  # type: ignore[arg-type]


def test_create_exam_category_succeeds_and_audits() -> None:
    categories = FakeExamCategoryRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateExamCategoryUseCase(categories=categories, audit=audit, clock=FakeClock(_NOW))

    result = use_case.execute(_create_command())

    assert result.name == "Hematologia"
    assert result.status == ExamCategoryStatus.ACTIVE.value
    assert categories.get_by_id(result.id) is not None
    assert audit.entries[0].action == "exam_categories.created"


def test_create_exam_category_without_permission_is_forbidden() -> None:
    categories = FakeExamCategoryRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateExamCategoryUseCase(categories=categories, audit=audit, clock=FakeClock(_NOW))

    with pytest.raises(ForbiddenError):
        use_case.execute(_create_command(actor=_actor(permissions=frozenset())))


def test_create_exam_category_with_duplicate_name_conflicts() -> None:
    categories = FakeExamCategoryRepository()
    audit = FakeAuditLogWriter()
    use_case = CreateExamCategoryUseCase(categories=categories, audit=audit, clock=FakeClock(_NOW))
    use_case.execute(_create_command())

    with pytest.raises(DuplicateExamCategoryNameError):
        use_case.execute(_create_command(name="  hematologia  "))


def test_update_exam_category_with_stale_row_version_conflicts() -> None:
    categories = FakeExamCategoryRepository()
    audit = FakeAuditLogWriter()
    created = CreateExamCategoryUseCase(
        categories=categories, audit=audit, clock=FakeClock(_NOW)
    ).execute(_create_command())

    use_case = UpdateExamCategoryUseCase(categories=categories, audit=audit, clock=FakeClock(_NOW))
    with pytest.raises(ConflictError):
        use_case.execute(
            UpdateExamCategoryCommand(
                actor=_actor(permissions=frozenset({"catalog.manage"})),
                category_id=created.id,
                name="Hematologia Renomeada",
                status=ExamCategoryStatus.ACTIVE.value,
                expected_row_version=created.row_version + 1,
            )
        )


def test_update_exam_category_succeeds_and_bumps_row_version() -> None:
    categories = FakeExamCategoryRepository()
    audit = FakeAuditLogWriter()
    created = CreateExamCategoryUseCase(
        categories=categories, audit=audit, clock=FakeClock(_NOW)
    ).execute(_create_command())

    use_case = UpdateExamCategoryUseCase(categories=categories, audit=audit, clock=FakeClock(_NOW))
    result = use_case.execute(
        UpdateExamCategoryCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})),
            category_id=created.id,
            name="Hematologia Renomeada",
            status=ExamCategoryStatus.ACTIVE.value,
            expected_row_version=created.row_version,
        )
    )

    assert result.name == "Hematologia Renomeada"
    assert result.row_version == created.row_version + 1
    assert audit.entries[-1].action == "exam_categories.updated"


def test_update_exam_category_not_found() -> None:
    categories = FakeExamCategoryRepository()
    audit = FakeAuditLogWriter()
    use_case = UpdateExamCategoryUseCase(categories=categories, audit=audit, clock=FakeClock(_NOW))

    with pytest.raises(NotFoundError):
        use_case.execute(
            UpdateExamCategoryCommand(
                actor=_actor(permissions=frozenset({"catalog.manage"})),
                category_id=uuid4(),
                name="Fantasma",
                status=ExamCategoryStatus.ACTIVE.value,
                expected_row_version=1,
            )
        )


def test_deactivate_exam_category_soft_deletes_and_preserves_record() -> None:
    categories = FakeExamCategoryRepository()
    audit = FakeAuditLogWriter()
    created = CreateExamCategoryUseCase(
        categories=categories, audit=audit, clock=FakeClock(_NOW)
    ).execute(_create_command())

    use_case = DeactivateExamCategoryUseCase(
        categories=categories, audit=audit, clock=FakeClock(_NOW)
    )
    result = use_case.execute(
        DeactivateExamCategoryCommand(
            actor=_actor(permissions=frozenset({"catalog.manage"})), category_id=created.id
        )
    )

    assert result.status == ExamCategoryStatus.INACTIVE.value
    stored = categories.get_by_id(created.id)
    assert stored is not None
    assert stored.name == created.name
    assert audit.entries[-1].action == "exam_categories.deactivated"


def test_list_exam_categories_requires_permission() -> None:
    categories = FakeExamCategoryRepository()
    use_case = ListExamCategoriesUseCase(categories=categories)

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ListExamCategoriesQuery(actor=_actor(permissions=frozenset()), page=1, page_size=20)
        )


def test_get_exam_category_not_found() -> None:
    categories = FakeExamCategoryRepository()
    use_case = GetExamCategoryUseCase(categories=categories)

    with pytest.raises(NotFoundError):
        use_case.execute(
            GetExamCategoryQuery(
                actor=_actor(permissions=frozenset({"catalog.read"})), category_id=uuid4()
            )
        )
