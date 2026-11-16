from __future__ import annotations

from datetime import time

import pytest

from app.modules.attendances.domain.fee_schedule import FeeSchedule
from app.shared.domain.errors import ValidationError


@pytest.mark.parametrize(
    ("schedule", "label"),
    [
        (FeeSchedule(), ""),
        (FeeSchedule(weekdays=tuple(range(7))), "Todos os dias"),
        (FeeSchedule(weekdays=(0, 1, 2, 3, 4)), "Seg-Sex"),
        (FeeSchedule(weekdays=(6, 5)), "Fim de semana"),
        (FeeSchedule(weekdays=(0, 2, 4)), "Seg, Qua, Sex"),
        (FeeSchedule(weekdays=(2,)), "Qua"),
        (FeeSchedule(start_time=time(18), end_time=time(7)), "18h às 07h"),
        (
            FeeSchedule(weekdays=(0, 1, 2), start_time=time(18, 30), end_time=time(7)),
            "Seg-Qua · 18:30 às 07h",
        ),
    ],
)
def test_label_is_generated_from_days_and_hours(schedule: FeeSchedule, label: str) -> None:
    assert schedule.label() == label


@pytest.mark.parametrize(
    "kwargs",
    [
        {"weekdays": (7,)},
        {"weekdays": (-1,)},
        {"weekdays": (1, 1)},
        {"start_time": time(8)},
        {"end_time": time(8)},
        {"start_time": time(8), "end_time": time(8)},
    ],
)
def test_invalid_schedules_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        FeeSchedule(**kwargs)  # type: ignore[arg-type]
