"""Dias da semana e horário (informativos) de uma taxa de plantão ou urgência.

É só contexto para quem registra o atendimento: o tipo do atendimento continua sendo
escolhido manualmente, então nada aqui entra no cálculo do total. `label()` gera o texto
mostrado nas telas (ex.: "Seg-Sex · 19h às 07h").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from app.shared.domain.errors import ValidationError

# 0 = segunda … 6 = domingo (mesmo critério de `date.weekday()`).
_DAY_NAMES = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


def _format_time(value: time) -> str:
    return f"{value.hour:02d}h" if value.minute == 0 else f"{value.hour:02d}:{value.minute:02d}"


def _format_days(days: tuple[int, ...]) -> str:
    if len(days) == 7:
        return "Todos os dias"
    if days == (5, 6):
        return "Fim de semana"
    contiguous = days[-1] - days[0] + 1 == len(days)
    if contiguous and len(days) >= 3:
        return f"{_DAY_NAMES[days[0]]}-{_DAY_NAMES[days[-1]]}"
    return ", ".join(_DAY_NAMES[day] for day in days)


def schedule_state(schedule: FeeSchedule) -> dict[str, object]:
    """Forma gravada no `audit_log` (antes/depois) para os campos de horário."""
    return {
        "weekdays": list(schedule.weekdays),
        "start_time": schedule.start_time.strftime("%H:%M") if schedule.start_time else None,
        "end_time": schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
    }


@dataclass(frozen=True)
class FeeSchedule:
    weekdays: tuple[int, ...] = ()
    start_time: time | None = None
    end_time: time | None = None

    def __post_init__(self) -> None:
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValidationError("Dia da semana inválido.")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValidationError("Dias da semana repetidos.")
        object.__setattr__(self, "weekdays", tuple(sorted(self.weekdays)))
        if (self.start_time is None) != (self.end_time is None):
            raise ValidationError("Informe o horário de início e o de fim.")
        if self.start_time is not None and self.start_time == self.end_time:
            raise ValidationError("O horário de fim deve ser diferente do início.")

    def is_empty(self) -> bool:
        return not self.weekdays and self.start_time is None

    def label(self) -> str:
        parts: list[str] = []
        if self.weekdays:
            parts.append(_format_days(self.weekdays))
        if self.start_time is not None and self.end_time is not None:
            parts.append(f"{_format_time(self.start_time)} às {_format_time(self.end_time)}")
        return " · ".join(parts)
