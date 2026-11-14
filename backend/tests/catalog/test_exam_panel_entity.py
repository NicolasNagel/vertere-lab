from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.value_objects import ExamCode

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_SPECIES = frozenset({uuid4()})


def _exam(*, exam_id: UUID | None = None, components: tuple[UUID, ...] = ()) -> Exam:
    return Exam(
        id=exam_id or uuid4(),
        code=ExamCode("ABCD1234"),
        name="Exame",
        category_id=uuid4(),
        price_base=Decimal("10.00"),
        species_ids=_SPECIES,
        component_ids=components,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _update(exam: Exam, components: tuple[UUID, ...]) -> None:
    exam.update_details(
        name=exam.name,
        category_id=exam.category_id,
        price_base=exam.price_base,
        description=None,
        species_ids=_SPECIES,
        component_ids=components,
        status=ExamStatus.ACTIVE,
        updated_by=None,
        now=_NOW,
    )


def test_exam_with_components_is_a_panel_and_without_is_not() -> None:
    assert _exam(components=(uuid4(),)).is_panel is True
    assert _exam().is_panel is False


def test_panel_cannot_contain_itself_or_repeat_components() -> None:
    own_id = uuid4()
    with pytest.raises(ValueError, match="ele mesmo"):
        _exam(exam_id=own_id, components=(own_id,))
    repeated = uuid4()
    with pytest.raises(ValueError, match="repetidos"):
        _exam(components=(repeated, repeated))


def test_exam_and_panel_cannot_be_converted_into_each_other() -> None:
    plain = _exam()
    with pytest.raises(ValueError, match="transformar"):
        _update(plain, (uuid4(),))
    panel = _exam(components=(uuid4(),))
    with pytest.raises(ValueError, match="transformar"):
        _update(panel, ())
    replacement = (uuid4(),)
    _update(panel, replacement)
    assert panel.component_ids == replacement
