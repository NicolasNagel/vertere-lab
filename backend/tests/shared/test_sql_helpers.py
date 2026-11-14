from __future__ import annotations

import pytest

from app.shared.infrastructure.sql import contains_pattern


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abc", "%abc%"),
        ("100%", r"%100\%%"),
        ("a_b", r"%a\_b%"),
        (r"a\b", r"%a\\b%"),
        ("%%", r"%\%\%%"),
        ("", "%%"),
    ],
)
def test_contains_pattern_escapes_like_metacharacters(raw: str, expected: str) -> None:
    assert contains_pattern(raw) == expected
