"""Numeric request fields shared by the money endpoints (limits live in `app.shared.domain.limits`).

Quantity and unit price had no ceiling, so a typo or a hostile request could overflow a
`NUMERIC(14,2)` column and answer 500.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from app.shared.domain.limits import (
    MAX_ITEMS_PER_ATTENDANCE,
    MAX_LINE_DISCOUNT,
    MAX_QUANTITY,
    MAX_UNIT_PRICE,
)

__all__ = ["MAX_ITEMS_PER_ATTENDANCE", "MAX_LINE_DISCOUNT", "MAX_UNIT_PRICE", "Quantity"]
_ = MAX_QUANTITY

Quantity = Annotated[int, Field(ge=1, le=MAX_QUANTITY)]
