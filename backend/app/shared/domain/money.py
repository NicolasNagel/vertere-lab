"""Centralized currency rounding — the single point in the domain that
rounds money (rule: .claude/rules/12-attendance.md, "moeda e arredondamento
centralizados em um único ponto do domínio")."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("0.01")


def round_currency(amount: Decimal) -> Decimal:
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)
