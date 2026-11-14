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
        user_id=uuid4(),
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


def test_exam_category_lifecycle_is_unique_versioned_audited_and_preserves_history() -> None:
    categories = FakeExamCategoryRepository()
    audit = FakeAuditLogWriter()
    create = CreateExamCategoryUseCase(categories=categories, audit=audit, clock=FakeClock(_NOW))
    update = UpdateExamCategoryUseCase(categories=categories, audit=audit, clock=FakeClock(_NOW))
    deactivate = DeactivateExamCategoryUseCase(
        categories=categories, audit=audit, clock=FakeClock(_NOW)
    )
    manager = _actor(permissions=frozenset({"catalog.manage"}))

    with pytest.raises(ForbiddenError):
        create.execute(_create_command(actor=_actor(permissions=frozenset())))
    created = create.execute(_create_command())
    assert created.name == "Hematologia"
    assert created.status == ExamCategoryStatus.ACTIVE.value
    assert categories.get_by_id(created.id) is not None
    assert audit.entries[0].action == "exam_categories.created"
    with pytest.raises(DuplicateExamCategoryNameError):  # nome único, sem diferenciar caixa
        create.execute(_create_command(name="  hematologia  "))

    def update_command(**overrides: object) -> UpdateExamCategoryCommand:
        fields: dict[str, object] = {
            "actor": manager,
            "category_id": created.id,
            "name": "Hematologia Renomeada",
            "status": ExamCategoryStatus.ACTIVE.value,
            "expected_row_version": created.row_version,
        }
        fields.update(overrides)
        return UpdateExamCategoryCommand(**fields)  # type: ignore[arg-type]

    with pytest.raises(ConflictError):
        update.execute(update_command(expected_row_version=created.row_version + 1))
    with pytest.raises(NotFoundError):
        update.execute(update_command(category_id=uuid4()))
    updated = update.execute(update_command())
    assert updated.name == "Hematologia Renomeada"
    assert updated.row_version == created.row_version + 1
    assert audit.entries[-1].action == "exam_categories.updated"

    result = deactivate.execute(
        DeactivateExamCategoryCommand(actor=manager, category_id=created.id)
    )
    assert result.status == ExamCategoryStatus.INACTIVE.value
    stored = categories.get_by_id(created.id)
    assert stored is not None
    assert stored.name == "Hematologia Renomeada"
    assert audit.entries[-1].action == "exam_categories.deactivated"


def test_list_and_get_exam_categories_require_permission_and_report_missing() -> None:
    categories = FakeExamCategoryRepository()
    nobody = _actor(permissions=frozenset())
    reader = _actor(permissions=frozenset({"catalog.read"}))

    with pytest.raises(ForbiddenError):
        ListExamCategoriesUseCase(categories=categories).execute(
            ListExamCategoriesQuery(actor=nobody, page=1, page_size=20)
        )
    with pytest.raises(NotFoundError):
        GetExamCategoryUseCase(categories=categories).execute(
            GetExamCategoryQuery(actor=reader, category_id=uuid4())
        )
