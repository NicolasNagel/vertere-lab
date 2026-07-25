"""Value objects for the veterinarians domain — immutable, self-validating."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Crmv:
    """Veterinarian registration number (CRMV) — normalized, non-empty.

    No checksum/format validation in this slice: unlike CNPJ, there is no
    single official CRMV digit algorithm (format varies by state council),
    and the product spec (assets/features/screens/spec-pages.md) does not
    define one. Only whitespace/case normalization + uniqueness (enforced
    by the repository/DB constraint) are applied here.
    """

    value: str

    def __post_init__(self) -> None:
        normalized = " ".join(self.value.split()).upper()
        if not normalized:
            raise ValueError("CRMV não pode ser vazio.")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
