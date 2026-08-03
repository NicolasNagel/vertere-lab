"""Value objects for the catalog domain — immutable, self-validating."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExamCode:
    """Exam catalog code — normalized, non-empty, unique per exam.

    Normalized the same way as `Crmv`
    (`app/modules/veterinarians/domain/value_objects.py`): whitespace
    collapsed, uppercased. No format/checksum validation — the spec
    (`assets/features/screens/spec-pages.md`, "Tela de Cadastro de Exames &
    Preços") only requires the code to be non-empty and unique, not a
    specific pattern.
    """

    value: str

    def __post_init__(self) -> None:
        normalized = " ".join(self.value.split()).upper()
        if not normalized:
            raise ValueError("Código do exame não pode ser vazio.")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
