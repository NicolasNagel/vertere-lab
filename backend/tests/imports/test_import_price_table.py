from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.imports.application.import_price_table import (
    ImportPriceTableCommand,
    ImportPriceTableUseCase,
)
from app.modules.imports.application.stage_price_table_pdf import SHEET_NAME
from app.shared.domain.errors import ForbiddenError
from tests.catalog.fakes import FakeAuditLogWriter, FakeExamRepository
from tests.imports.fakes import FakeClock, FakeImportStagingRowRepository, make_staging_row

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _exam(*, name: str, price: Decimal, category_id: UUID | None = None) -> Exam:
    return Exam(
        id=uuid4(),
        code=ExamCode("".join(ch for ch in name.upper() if ch.isalnum())),
        name=name,
        category_id=category_id or uuid4(),
        price_base=price,
        species_ids=frozenset({uuid4()}),
        status=ExamStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _use_case(
    *,
    staging_rows: FakeImportStagingRowRepository,
    exams: FakeExamRepository,
    audit: FakeAuditLogWriter,
) -> ImportPriceTableUseCase:
    return ImportPriceTableUseCase(
        staging_rows=staging_rows, exams=exams, audit=audit, clock=FakeClock(_NOW)
    )


def test_without_permission_is_forbidden() -> None:
    use_case = _use_case(
        staging_rows=FakeImportStagingRowRepository(),
        exams=FakeExamRepository(),
        audit=FakeAuditLogWriter(),
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(
            ImportPriceTableCommand(
                actor_id=uuid4(), actor_permissions=frozenset(), batch_id=uuid4()
            )
        )


def test_updates_price_when_pdf_value_differs_from_catalog() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=1,
                raw_data={
                    "category": "Exames Hematológicos",
                    "name": "Hemograma",
                    "price": "30.00",
                },
            )
        ]
    )
    exams = FakeExamRepository()
    exam = _exam(name="Hemograma", price=Decimal("28.00"))
    exams.add(exam)
    audit = FakeAuditLogWriter()

    result = _use_case(staging_rows=staging_rows, exams=exams, audit=audit).execute(
        ImportPriceTableCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    assert result.skipped_existing_count == 0
    assert result.exceptions == ()
    updated_exam = exams.get_by_id(exam.id)
    assert updated_exam is not None
    assert updated_exam.price_base == Decimal("30.00")
    assert len(audit.entries) == 1
    assert audit.entries[0].action == "exams.price_updated_from_price_table"
    assert audit.entries[0].before_state == {"price_base": "28.00"}


def test_same_price_is_a_no_op_not_re_audited() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=1,
                raw_data={"category": "perfis", "name": "Básico 1", "price": "60.00"},
            )
        ]
    )
    exams = FakeExamRepository()
    exam = _exam(name="Básico 1", price=Decimal("60.00"))
    exams.add(exam)
    audit = FakeAuditLogWriter()

    result = _use_case(staging_rows=staging_rows, exams=exams, audit=audit).execute(
        ImportPriceTableCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert result.skipped_existing_count == 1
    assert audit.entries == []


def test_name_not_found_in_catalog_becomes_an_exception_never_creates_an_exam() -> None:
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=1,
                raw_data={
                    "category": "Exames Urinários",
                    "name": "Exame Inexistente",
                    "price": "25.00",
                },
            )
        ]
    )
    exams = FakeExamRepository()

    result = _use_case(staging_rows=staging_rows, exams=exams, audit=FakeAuditLogWriter()).execute(
        ImportPriceTableCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert "não encontrado no catálogo" in result.exceptions[0].message
    assert (
        exams.list_page(
            page=1, page_size=50, status=None, category_id=None, species_id=None, search=None
        )[1]
        == 0
    )


def test_accent_and_case_only_difference_still_matches() -> None:
    # PDF spells it "Basico 1" (no accent) vs catalog "Básico 1" — same fold-key pattern as
    # import_exams_from_history.py.
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id,
                sheet_name=SHEET_NAME,
                source_row_number=1,
                raw_data={"category": "perfis", "name": "basico 1", "price": "65.00"},
            )
        ]
    )
    exams = FakeExamRepository()
    exam = _exam(name="Básico 1", price=Decimal("60.00"))
    exams.add(exam)

    result = _use_case(staging_rows=staging_rows, exams=exams, audit=FakeAuditLogWriter()).execute(
        ImportPriceTableCommand(
            actor_id=uuid4(), actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert result.imported_count == 1
    updated_exam = exams.get_by_id(exam.id)
    assert updated_exam is not None
    assert updated_exam.price_base == Decimal("65.00")
