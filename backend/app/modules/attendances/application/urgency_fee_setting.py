"""Read and edit the single urgency fee (fixed amount charged once on an urgent attendance).

Same shape as `update_on_call_fee_setting.py`: lab scope only, `pricing.read` to see,
`pricing.manage` to change, row-version conflict, mandatory reason, audit with before/after.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.modules.attendances.domain.entities import UrgencyFeeSetting
from app.modules.attendances.domain.fee_schedule import FeeSchedule, schedule_state
from app.modules.attendances.domain.repositories import UrgencyFeeSettingRepository
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

_READ_PERMISSION = "pricing.read"
_MANAGE_PERMISSION = "pricing.manage"


def _require(actor: ActorContext, permission: str) -> None:
    if actor.role_scope == "CLINIC":
        raise ForbiddenError("Taxas são exclusivas do laboratório.")
    if permission not in actor.permissions:
        raise ForbiddenError(f"Permissão ausente: {permission}")


@dataclass(frozen=True, kw_only=True)
class GetUrgencyFeeSettingQuery:
    actor: ActorContext


class GetUrgencyFeeSettingUseCase:
    def __init__(self, *, urgency_fee: UrgencyFeeSettingRepository) -> None:
        self._urgency_fee = urgency_fee

    def execute(self, query: GetUrgencyFeeSettingQuery) -> UrgencyFeeSetting:
        _require(query.actor, _READ_PERMISSION)
        setting = self._urgency_fee.get()
        if setting is None:
            raise NotFoundError("Configuração de taxa de urgência não encontrada.")
        return setting


@dataclass(frozen=True, kw_only=True)
class UpdateUrgencyFeeSettingCommand:
    actor: ActorContext
    fee_amount: Decimal
    schedule: FeeSchedule
    reason: str
    expected_row_version: int


class UpdateUrgencyFeeSettingUseCase:
    def __init__(
        self, *, urgency_fee: UrgencyFeeSettingRepository, audit: AuditLogWriter, clock: Clock
    ) -> None:
        self._urgency_fee = urgency_fee
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdateUrgencyFeeSettingCommand) -> UrgencyFeeSetting:
        _require(command.actor, _MANAGE_PERMISSION)
        reason = command.reason.strip()
        if not reason:
            raise ValidationError("Informe o motivo da alteração.")

        setting = self._urgency_fee.get()
        if setting is None:
            raise NotFoundError("Configuração de taxa de urgência não encontrada.")
        if setting.row_version != command.expected_row_version:
            raise ConflictError(
                "Esta configuração foi alterada por outra pessoa. Recarregue e tente de novo."
            )

        before_state = {
            "fee_amount": str(setting.fee_amount),
            "schedule_label": setting.schedule_label,
            **schedule_state(setting.schedule),
        }
        setting.update(
            fee_amount=command.fee_amount,
            schedule=command.schedule,
            now=self._clock.now(),
            updated_by=command.actor.id,
        )
        self._urgency_fee.update(setting)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="urgency_fee_settings.updated",
                entity_type="urgency_fee_setting",
                entity_id=str(setting.id),
                before_state=before_state,
                after_state={
                    "fee_amount": str(setting.fee_amount),
                    "schedule_label": setting.schedule_label,
                    **schedule_state(setting.schedule),
                },
                reason=reason,
            )
        )
        return setting
