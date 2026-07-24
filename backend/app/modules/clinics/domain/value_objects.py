"""Value objects for the clinics domain — immutable, self-validating."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TAX_ID_DIGITS_PATTERN = re.compile(r"^\d{14}$")


@dataclass(frozen=True, slots=True)
class TaxId:
    """CNPJ — digits only, normalized. No checksum validation in this slice
    (no explicit requirement for it yet; the format check catches the most
    common data-entry mistakes without blocking a real, valid CNPJ)."""

    value: str

    def __post_init__(self) -> None:
        digits = re.sub(r"\D", "", self.value)
        if not _TAX_ID_DIGITS_PATTERN.match(digits):
            raise ValueError(f"CNPJ inválido: {self.value!r}")
        object.__setattr__(self, "value", digits)

    def __str__(self) -> str:
        return self.value
