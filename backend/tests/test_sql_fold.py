from __future__ import annotations

import pytest

from app.shared.infrastructure.sql import fold


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("João", "joao"), ("CONCEIÇÃO", "conceicao"), ("Ünïcödé", "unicode"), ("abc 123", "abc 123")],
)
def test_fold_lowercases_and_strips_accents(raw: str, expected: str) -> None:
    assert fold(raw) == expected
