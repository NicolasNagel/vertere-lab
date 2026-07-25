"""Value objects for the catalog domain — immutable, self-validating."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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


@dataclass(frozen=True, slots=True)
class PlantaoSurcharge:
    """At most one of `fixed_amount`/`percent` is set — the spec describes
    the adicional de plantão as "percentual ou valor fixo", i.e. mutually
    exclusive, not additive.
    """

    fixed_amount: Decimal | None = None
    percent: Decimal | None = None

    def __post_init__(self) -> None:
        if self.fixed_amount is not None and self.percent is not None:
            raise ValueError("Adicional de plantão aceita valor fixo OU percentual, não os dois.")
        if self.fixed_amount is not None and self.fixed_amount <= 0:
            raise ValueError("Adicional de plantão em valor fixo deve ser maior que zero.")
        if self.percent is not None and not (Decimal("0") < self.percent <= Decimal("100")):
            raise ValueError("Adicional de plantão em percentual deve estar entre 0 e 100.")

    @property
    def is_empty(self) -> bool:
        return self.fixed_amount is None and self.percent is None
