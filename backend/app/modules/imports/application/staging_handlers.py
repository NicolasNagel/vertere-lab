"""Atomic handlers for import staging."""

from __future__ import annotations

from app.modules.imports.application.stage_price_table_pdf import (
    StagePriceTablePdfCommand,
    StagePriceTablePdfResult,
    StagePriceTablePdfUseCase,
)
from app.modules.imports.application.stage_spreadsheet import (
    StageSpreadsheetCommand,
    StageSpreadsheetResult,
    StageSpreadsheetUseCase,
)
from app.modules.imports.application.uow import ImportUnitOfWork
from app.shared.application.clock import Clock


def handle_stage_spreadsheet(
    *, uow: ImportUnitOfWork, command: StageSpreadsheetCommand, clock: Clock
) -> StageSpreadsheetResult:
    with uow:
        result = StageSpreadsheetUseCase(
            batches=uow.batches, staging_rows=uow.staging_rows, clock=clock
        ).execute(command)
        uow.commit()
        return result


def handle_stage_price_table_pdf(
    *, uow: ImportUnitOfWork, command: StagePriceTablePdfCommand, clock: Clock
) -> StagePriceTablePdfResult:
    with uow:
        result = StagePriceTablePdfUseCase(
            batches=uow.batches, staging_rows=uow.staging_rows, clock=clock
        ).execute(command)
        uow.commit()
        return result
