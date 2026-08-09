"""List the two configurable on-call fee tiers — read side of
`OnCallFeeSetting` (`domain/entities.py`). Part of the "Exames & Preços"
mockup-fidelity plan (Fatia 2): the flat plantão fee, previously hardcoded
in `ON_CALL_FEES`, is now stored and editable via
`update_on_call_fee_setting.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.attendances.domain.entities import OnCallFeeSetting
from app.modules.attendances.domain.repositories import OnCallFeeSettingRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "pricing.read"


@dataclass(frozen=True, kw_only=True)
class GetOnCallFeeSettingsQuery:
    actor: ActorContext


class GetOnCallFeeSettingsUseCase:
    def __init__(self, *, on_call_fees: OnCallFeeSettingRepository) -> None:
        self._on_call_fees = on_call_fees

    def execute(self, query: GetOnCallFeeSettingsQuery) -> list[OnCallFeeSetting]:
        if _REQUIRED_PERMISSION not in query.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")
        return self._on_call_fees.list_all()
