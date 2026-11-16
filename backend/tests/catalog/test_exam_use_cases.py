from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.catalog.application.create_exam import CreateExamCommand, CreateExamUseCase
from app.modules.catalog.application.create_exam_category import (
    CreateExamCategoryCommand,
    CreateExamCategoryUseCase,
)
from app.modules.catalog.application.deactivate_exam import (
    DeactivateExamCommand,
    DeactivateExamUseCase,
)
from app.modules.catalog.application.dtos import ExamCategoryDTO
from app.modules.catalog.application.get_exam import GetExamQuery, GetExamUseCase
from app.modules.catalog.application.list_exams import ListExamsQuery, ListExamsUseCase
from app.modules.catalog.application.update_exam import UpdateExamCommand, UpdateExamUseCase
from app.modules.catalog.domain.entities import ExamStatus
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.domain.entities import Species
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from tests.catalog.fakes import (
    FakeAuditLogWriter,
    FakeClock,
    FakeExamCategoryRepository,
    FakeExamRepository,
    FakeSpeciesRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_DOG_SPECIES_ID = uuid4()
_CAT_SPECIES_ID = uuid4()


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="user@vertere.local",
        full_name="User",
        role_id=uuid4(),
        role_name="FINANCE",
        permissions=permissions,
    )


def _species_repo() -> FakeSpeciesRepository:
    return FakeSpeciesRepository(
        [
            Species(id=_DOG_SPECIES_ID, name="Cão", created_at=_NOW),
            Species(id=_CAT_SPECIES_ID, name="Gato", created_at=_NOW),
        ]
    )


def _seed_category(categories: FakeExamCategoryRepository) -> ExamCategoryDTO:
    audit = FakeAuditLogWriter()
    return CreateExamCategoryUseCase(
        categories=categories, audit=audit, clock=FakeClock(_NOW)
    ).execute(
        CreateExamCategoryCommand(
            actor=_actor(permissions=frozenset({"catalog.manage", "pricing.manage"})),
            name="Hematologia",
        )
    )


def _create_command(category_id: object, **overrides: object) -> CreateExamCommand:
    defaults: dict[str, object] = {
        "actor": _actor(
            permissions=frozenset({"catalog.manage", "pricing.manage", "pricing.read"})
        ),
        "name": "Hemograma completo",
        "category_id": category_id,
        "price_base": Decimal("85.00"),
        "description": None,
        "species_ids": frozenset({_DOG_SPECIES_ID}),
    }
    defaults.update(overrides)
    return CreateExamCommand(**defaults)  # type: ignore[arg-type]


def _exam_use_cases(
    categories: FakeExamCategoryRepository,
    exams: FakeExamRepository,
    audit: FakeAuditLogWriter,
    *,
    code_generator: Callable[[], str] | None = None,
) -> tuple[CreateExamUseCase, UpdateExamUseCase]:
    shared: dict[str, object] = {
        "exams": exams,
        "categories": categories,
        "species": _species_repo(),
        "audit": audit,
        "clock": FakeClock(_NOW),
    }
    extra: dict[str, object] = {} if code_generator is None else {"code_generator": code_generator}
    create = CreateExamUseCase(**shared, **extra)  # type: ignore[arg-type]
    update = UpdateExamUseCase(**shared)  # type: ignore[arg-type]
    return create, update


def test_create_exam_validates_references_retries_code_collisions_and_audits() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    generated_codes = iter(("HEM001", "HEM001", "BIO00001"))
    create, _ = _exam_use_cases(
        categories, exams, audit, code_generator=lambda: next(generated_codes)
    )

    with pytest.raises(ForbiddenError):
        create.execute(_create_command(category.id, actor=_actor(permissions=frozenset())))
    with pytest.raises(NotFoundError):
        create.execute(_create_command(uuid4()))
    with pytest.raises(ValidationError):
        create.execute(_create_command(category.id, species_ids=frozenset({uuid4()})))
    assert not audit.entries

    first = create.execute(_create_command(category.id))
    assert first.code == "HEM001"
    assert first.price_base == Decimal("85.00")
    assert first.status == ExamStatus.ACTIVE.value
    assert audit.entries[0].action == "exams.created"

    # Colisão do código gerado: tenta de novo até achar um livre.
    second = create.execute(_create_command(category.id, name="Outro exame"))
    assert second.code == "BIO00001"


def test_exam_price_is_hidden_without_pricing_permission_and_list_needs_permission() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    create, _ = _exam_use_cases(categories, exams, FakeAuditLogWriter())
    created = create.execute(_create_command(category.id))
    get = GetExamUseCase(exams=exams)

    without_price = get.execute(
        GetExamQuery(actor=_actor(permissions=frozenset({"catalog.read"})), exam_id=created.id)
    )
    with_price = get.execute(
        GetExamQuery(
            actor=_actor(permissions=frozenset({"catalog.read", "pricing.read"})),
            exam_id=created.id,
        )
    )
    assert without_price.price_base is None
    assert with_price.price_base == Decimal("85.00")
    with pytest.raises(ForbiddenError):
        ListExamsUseCase(exams=exams).execute(
            ListExamsQuery(actor=_actor(permissions=frozenset()), page=1, page_size=20)
        )


def test_exam_update_is_versioned_and_deactivation_preserves_the_record() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    create, update = _exam_use_cases(categories, exams, audit)
    created = create.execute(_create_command(category.id))

    with pytest.raises(ConflictError):
        update.execute(
            UpdateExamCommand(
                actor=_actor(permissions=frozenset({"catalog.manage", "pricing.manage"})),
                exam_id=created.id,
                name="Hemograma completo renomeado",
                category_id=category.id,
                price_base=Decimal("90.00"),
                description=None,
                species_ids=frozenset({_DOG_SPECIES_ID}),
                status=ExamStatus.ACTIVE.value,
                expected_row_version=created.row_version + 1,
            )
        )

    result = DeactivateExamUseCase(exams=exams, audit=audit, clock=FakeClock(_NOW)).execute(
        DeactivateExamCommand(
            actor=_actor(
                permissions=frozenset({"catalog.manage", "pricing.manage", "pricing.read"})
            ),
            exam_id=created.id,
        )
    )
    assert result.status == ExamStatus.INACTIVE.value
    stored = exams.get_by_id(created.id)
    assert stored is not None
    assert stored.name == created.name


def test_price_change_needs_pricing_manage_and_a_reason_and_is_audited() -> None:
    categories = FakeExamCategoryRepository()
    category = _seed_category(categories)
    exams = FakeExamRepository()
    audit = FakeAuditLogWriter()
    create, update = _exam_use_cases(categories, exams, audit)
    created = create.execute(_create_command(category.id))

    def _version(exam_id: UUID) -> int:
        stored_exam = exams.get_by_id(exam_id)
        assert stored_exam is not None
        return stored_exam.row_version

    def command(
        permissions: frozenset[str], *, price: Decimal | None, name: str, reason: str | None
    ) -> UpdateExamCommand:
        return UpdateExamCommand(
            actor=_actor(permissions=permissions),
            exam_id=created.id,
            name=name,
            category_id=category.id,
            price_base=price,
            description=None,
            species_ids=frozenset({_DOG_SPECIES_ID}),
            status=ExamStatus.ACTIVE.value,
            expected_row_version=_version(created.id),
            reason=reason,
        )

    catalog_only = frozenset({"catalog.manage"})
    # Sem pricing.manage: renomear (sem enviar preço) passa; mudar o preço não.
    renamed = update.execute(command(catalog_only, price=None, name="Renomeado", reason=None))
    assert renamed.name == "Renomeado"
    with pytest.raises(ForbiddenError):
        update.execute(
            command(catalog_only, price=Decimal("1.00"), name="Renomeado", reason="Ajuste")
        )

    manager = frozenset({"catalog.manage", "pricing.manage"})
    with pytest.raises(ValidationError):
        update.execute(command(manager, price=Decimal("1.00"), name="Renomeado", reason=None))

    stored = exams.get_by_id(created.id)
    assert stored is not None
    current = UpdateExamCommand(
        actor=_actor(permissions=manager),
        exam_id=created.id,
        name="Renomeado",
        category_id=category.id,
        price_base=Decimal("1.00"),
        description=None,
        species_ids=frozenset({_DOG_SPECIES_ID}),
        status=ExamStatus.ACTIVE.value,
        expected_row_version=stored.row_version,
        reason="Reajuste anual",
    )
    update.execute(current)
    last = audit.entries[-1]
    assert last.reason == "Reajuste anual"
    assert last.before_state is not None and last.after_state is not None
    assert last.before_state["price_base"] != last.after_state["price_base"]
