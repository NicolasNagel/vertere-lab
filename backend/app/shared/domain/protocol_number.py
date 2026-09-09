"""Business protocol formatting without persistence or framework dependencies."""

from __future__ import annotations

import re

_HISTORICAL_PROTOCOL_PATTERN = re.compile(r"^(?P<year>\d{4})/(?P<sequence>\d{6})$")


def format_protocol_number(*, year: int, sequence: int) -> str:
    """Format a newly issued annual attendance protocol."""
    return f"P{sequence:06d}/{year % 100:02d}"


def present_protocol_number(protocol_number: str | None) -> str | None:
    """Present historical values in the current format without rewriting storage."""
    if protocol_number is None:
        return None
    match = _HISTORICAL_PROTOCOL_PATTERN.fullmatch(protocol_number)
    if match is None:
        return protocol_number
    return format_protocol_number(
        year=int(match.group("year")),
        sequence=int(match.group("sequence")),
    )
