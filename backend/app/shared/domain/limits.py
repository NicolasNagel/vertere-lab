"""Business limits on client-supplied numbers, shared by the API schemas and the import use cases.

Decided with the product owner: a line quantity up to 999 and a unit price up to R$ 99.999,99. They sit
far above real use and far below `NUMERIC(14,2)`, so a line total and a month's sum cannot overflow.
"""

from __future__ import annotations

from decimal import Decimal

MAX_QUANTITY = 999
MAX_UNIT_PRICE = Decimal("99999.99")
# A line discount cannot exceed the largest possible line (quantity x unit price).
MAX_LINE_DISCOUNT = MAX_UNIT_PRICE * MAX_QUANTITY
# 100 lines x the largest line (~R$ 100 mi) stays far below NUMERIC(14,2) (~R$ 1 tri).
MAX_ITEMS_PER_ATTENDANCE = 100
