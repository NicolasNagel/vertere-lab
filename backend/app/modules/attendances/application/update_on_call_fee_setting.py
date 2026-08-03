"""Edit one on-call fee tier's amount/schedule label — write side of
`OnCallFeeSetting`. Reverts the "não configurável" decision from commit
c8b4a19e per explicit product decision (see plan
`dentro-da-pasta-assets-enchanted-narwhal.md`): the fee amount is now a
persisted, audited, permission-gated setting instead of a hardcoded
constant. Follows the same shape as
`app/modules/catalog/application/update_exam.py` (row-version conflict,
audit entry, `pricing.manage` gate).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.modules.attendances.domain.entities import OnCallFeeSetting, ServiceLevel
from app.modules.attendances.domain.repositories import OnCallFeeSettingRepository
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "pricing.manage"


@dataclass(frozen=True, kw_only=True)
class UpdateOnCallFeeSettingCommand:
    actor: AuthenticatedUserDTO
    service_level: ServiceLevel
    fee_amount: Decimal
    schedule_label: str
    expected_row_version: int


class UpdateOnCallFeeSettingUseCase:
    def __init__(
        self, *, on_call_fees: OnCallFeeSettingRepository, audit: AuditLogWriter, clock: Clock
    ) -> None:
        self._on_call_fees = on_call_fees
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdateOnCallFeeSettingCommand) -> OnCallFeeSetting:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        if command.service_level == ServiceLevel.NORMAL:
            raise ValidationError("NORMAL não tem taxa de plantão configurável.")

        setting = self._on_call_fees.get_by_service_level(command.service_level)
        if setting is None:
            raise NotFoundError("Configuração de taxa de plantão não encontrada.")
        if setting.row_version != command.expected_row_version:
            raise ConflictError(
                "Esta configuração foi alterada por outra pessoa. Recarregue e tente de novo."
            )

        before_state = {
            "fee_amount": str(setting.fee_amount),
            "schedule_label": setting.schedule_label,
        }

        setting.update(
            fee_amount=command.fee_amount,
            schedule_label=command.schedule_label,
            now=self._clock.now(),
            updated_by=command.actor.id,
        )
        self._on_call_fees.update(setting)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="on_call_fee_settings.updated",
                entity_type="on_call_fee_setting",
                entity_id=str(setting.id),
                before_state=before_state,
                after_state={
                    "fee_amount": str(setting.fee_amount),
                    "schedule_label": setting.schedule_label,
                },
            )
        )

        return setting
