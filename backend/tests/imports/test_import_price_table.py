from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.imports.application.import_price_table import (
    ImportPriceTableCommand,
    ImportPriceTableResult,
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


def _run(
    *rows: dict[str, str],
    catalog: dict[str, str],
    permissions: frozenset[str] = frozenset({"imports.execute"}),
) -> tuple[ImportPriceTableResult, FakeExamRepository, FakeAuditLogWriter, dict[str, Exam]]:
    """Stage PDF price rows and run the import against a `{name: price}` catalog."""
    batch_id = uuid4()
    staging_rows = FakeImportStagingRowRepository()
    staging_rows.add_many(
        [
            make_staging_row(
                batch_id=batch_id, sheet_name=SHEET_NAME, source_row_number=index + 1, raw_data=row
            )
            for index, row in enumerate(rows)
        ]
    )
    exams = FakeExamRepository()
    by_name = {name: _exam(name=name, price=Decimal(price)) for name, price in catalog.items()}
    for exam in by_name.values():
        exams.add(exam)
    audit = FakeAuditLogWriter()
    result = _use_case(staging_rows=staging_rows, exams=exams, audit=audit).execute(
        ImportPriceTableCommand(actor_id=uuid4(), actor_permissions=permissions, batch_id=batch_id)
    )
    return result, exams, audit, by_name


def test_price_table_import_requires_permission() -> None:
    with pytest.raises(ForbiddenError):
        _run(catalog={}, permissions=frozenset())


def test_price_table_import_updates_changed_prices_and_audits_only_real_changes() -> None:
    result, exams, audit, catalog = _run(
        {"category": "Exames Hematológicos", "name": "Hemograma", "price": "30.00"},
        {"category": "perfis", "name": "Básico 1", "price": "60.00"},  # preço igual: no-op
        # O PDF grafa "basico 1" sem acento/caixa: ainda casa pelo mesmo critério de dobra
        # de `import_exams_from_history.py`.
        {"category": "perfis", "name": "basico 2", "price": "65.00"},
        catalog={"Hemograma": "28.00", "Básico 1": "60.00", "Básico 2": "60.00"},
    )

    assert (result.imported_count, result.skipped_existing_count, result.exceptions) == (2, 1, ())
    for name, expected in (("Hemograma", "30.00"), ("Básico 1", "60.00"), ("Básico 2", "65.00")):
        stored = exams.get_by_id(catalog[name].id)
        assert stored is not None
        assert stored.price_base == Decimal(expected), name
    assert [entry.action for entry in audit.entries] == ["exams.price_updated_from_price_table"] * 2
    assert audit.entries[0].before_state == {"price_base": "28.00"}  # só mudanças reais auditadas


def test_price_table_import_never_creates_exams_missing_from_the_catalog() -> None:
    result, exams, audit, _ = _run(
        {"category": "Exames Urinários", "name": "Exame Inexistente", "price": "25.00"},
        catalog={},
    )

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert "não encontrado no catálogo" in result.exceptions[0].message
    assert audit.entries == []
    assert (
        exams.list_page(
            page=1, page_size=50, status=None, category_id=None, species_id=None, search=None
        )[1]
        == 0
    )
