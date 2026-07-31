from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.imports.application.stage_price_table_pdf import (
    SHEET_NAME,
    StagePriceTablePdfCommand,
    StagePriceTablePdfUseCase,
)
from app.modules.imports.infrastructure.pdf_price_table_reader import (
    PriceTableItem,
    PriceTableParseResult,
)
from app.shared.domain.errors import ForbiddenError, ValidationError
from tests.imports.fakes import FakeClock, FakeImportBatchRepository, FakeImportStagingRowRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _use_case(
    *,
    batches: FakeImportBatchRepository | None = None,
    staging_rows: FakeImportStagingRowRepository | None = None,
) -> StagePriceTablePdfUseCase:
    return StagePriceTablePdfUseCase(
        batches=batches or FakeImportBatchRepository(),
        staging_rows=staging_rows or FakeImportStagingRowRepository(),
        clock=FakeClock(_NOW),
    )


def test_stage_without_permission_is_forbidden() -> None:
    use_case = _use_case()

    with pytest.raises(ForbiddenError):
        use_case.execute(
            StagePriceTablePdfCommand(
                actor_id=uuid4(),
                actor_permissions=frozenset(),
                source_filename="tabela.pdf",
                content=b"not a real pdf",
            )
        )


def test_invalid_pdf_content_becomes_a_validation_error() -> None:
    use_case = _use_case()

    with pytest.raises(ValidationError):
        use_case.execute(
            StagePriceTablePdfCommand(
                actor_id=uuid4(),
                actor_permissions=frozenset({"imports.execute"}),
                source_filename="tabela.pdf",
                content=b"this is not a pdf file at all",
            )
        )


def test_restaging_the_same_content_returns_the_existing_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batches = FakeImportBatchRepository()
    staging_rows = FakeImportStagingRowRepository()
    use_case = _use_case(batches=batches, staging_rows=staging_rows)

    parsed_items: list[bytes] = []

    def fake_read_price_table(content: bytes) -> PriceTableParseResult:
        parsed_items.append(content)
        return PriceTableParseResult(
            items=(
                PriceTableItem(page=1, category="perfis", name="Hemograma", price=Decimal("28.00")),
            ),
            ignored_surcharge_lines=(),
            unpaired_lines=(),
        )

    monkeypatch.setattr(
        "app.modules.imports.application.stage_price_table_pdf.read_price_table",
        fake_read_price_table,
    )

    command = StagePriceTablePdfCommand(
        actor_id=uuid4(),
        actor_permissions=frozenset({"imports.execute"}),
        source_filename="tabela.pdf",
        content=b"same-bytes",
    )

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first.already_staged is False
    assert second.already_staged is True
    assert second.batch.id == first.batch.id
    assert len(parsed_items) == 1  # the reader is never called again for a known checksum
    assert len(staging_rows.list_by_batch(first.batch.id, sheet_name=SHEET_NAME)) == 1
