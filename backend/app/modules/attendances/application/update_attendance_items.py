"""Correct the exams of a CONFIRMED or CANCELLED attendance — add, remove, change
quantity or discount (`PUT /attendances/{id}/items`).

The request carries the complete desired set. Lines left out are not deleted: they
stay as `CANCELLED` so history keeps showing what was there. A new exam is priced on
the attendance's service date and frozen as a snapshot, like at confirmation; an
existing line keeps its snapshot price. A reason is mandatory and the audit entry
carries the before/after of the items and of the grand total.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.modules.attendances.application.attendance_items import (
    AttendanceItemInput,
    require_discount_authority,
    resolve_clinic_fee_lines,
    snapshot_item,
)
from app.modules.attendances.application.closure_settlement import (
    ClosureSettlement,
    FinancialPosition,
)
from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.domain.entities import (
    AttendanceExam,
    AttendanceExamStatus,
    AttendanceRecord,
    AttendanceStatus,
)
from app.modules.attendances.domain.repositories import (
    AttendanceRepository,
    ClinicFeeRuleRepository,
)
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "attendances.update"


@dataclass(frozen=True, kw_only=True)
class AttendanceItemEdit:
    item_id: UUID | None = None
    exam_id: UUID | None = None
    quantity: int = 1
    discount_amount: Decimal | None = None
    override_reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class UpdateAttendanceItemsCommand:
    actor: ActorContext
    attendance_id: UUID
    expected_row_version: int
    reason: str
    items: list[AttendanceItemEdit]


class UpdateAttendanceItemsUseCase:
    def __init__(
        self,
        *,
        attendances: AttendanceRepository,
        exams: ExamRepository,
        clinic_fee_rules: ClinicFeeRuleRepository,
        closure_settlement: ClosureSettlement,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._attendances = attendances
        self._exams = exams
        self._clinic_fee_rules = clinic_fee_rules
        self._closure_settlement = closure_settlement
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdateAttendanceItemsCommand) -> AttendanceDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        attendance = self._attendances.get_by_id(command.attendance_id)
        if attendance is None or not command.actor.can_access_clinic(attendance.clinic_id):
            raise NotFoundError("Atendimento não encontrado.")
        if command.expected_row_version != attendance.row_version:
            raise ConflictError(
                "O atendimento foi alterado por outra operação. Recarregue e tente novamente."
            )
        reason = command.reason.strip()
        if not reason:
            raise ValidationError("Informe o motivo da alteração.")

        before = _summary(attendance)
        position = FinancialPosition.of(attendance)
        new_items = self._build_items(attendance, command)
        attendance.apply_item_changes(
            items=new_items,
            now=self._clock.now(),
            updated_by=command.actor.id,
            closed_correction=True,
        )
        if attendance.status == AttendanceStatus.CONFIRMED:
            # Which clinic rules match depends on the exams: re-resolve them (plantão and
            # urgência stay frozen); a rule edited later never reaches an attendance not edited.
            assert attendance.service_date is not None
            attendance.replace_clinic_fees(
                lines=resolve_clinic_fee_lines(
                    service_level=attendance.service_level,
                    is_urgent=attendance.is_urgent,
                    clinic_id=attendance.clinic_id,
                    service_date=attendance.service_date,
                    exam_ids=[
                        item.exam_id
                        for item in attendance.items
                        if item.status == AttendanceExamStatus.ACTIVE
                    ],
                    clinic_fee_rules=self._clinic_fee_rules,
                ),
                now=self._clock.now(),
                updated_by=command.actor.id,
            )
        after = _summary(attendance)
        if after == before:
            return attendance_to_dto(attendance)
        if position.needs_settlement(attendance):
            self._closure_settlement.settle(
                actor=command.actor, attendance=attendance, before=position, reason=reason
            )
        self._attendances.update(attendance)
        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="attendances.items_updated",
                entity_type="attendance",
                entity_id=str(attendance.id),
                before_state=before,
                after_state=after,
                reason=reason,
            )
        )
        return attendance_to_dto(attendance)

    def _build_items(
        self, attendance: AttendanceRecord, command: UpdateAttendanceItemsCommand
    ) -> list[AttendanceExam]:
        existing = {item.id: item for item in attendance.items}
        kept: set[UUID] = set()
        result: list[AttendanceExam] = []
        for line in command.items:
            if line.item_id is not None:
                result.append(self._revise(existing, kept, line, command.actor))
            elif line.exam_id is not None:
                result.append(
                    snapshot_item(
                        attendance=attendance,
                        item_input=AttendanceItemInput(
                            exam_id=line.exam_id,
                            quantity=line.quantity,
                            discount_amount=line.discount_amount
                            if "pricing.read" in command.actor.permissions
                            else None,
                            override_reason=line.override_reason,
                        ),
                        actor=command.actor,
                        exams=self._exams,
                    )
                )
            else:
                raise ValidationError("Cada linha precisa de item_id ou exam_id.")

        for item_id, item in existing.items():
            if item_id in kept:
                continue
            item.revise(
                quantity=item.quantity,
                discount_amount=item.discount_amount,
                override_reason=item.override_reason,
                override_by=item.override_by,
                status=AttendanceExamStatus.CANCELLED,
            )
            result.append(item)

        if not any(item.status == AttendanceExamStatus.ACTIVE for item in result):
            raise ValidationError("O atendimento precisa ter ao menos um exame.")
        return result

    @staticmethod
    def _revise(
        existing: dict[UUID, AttendanceExam],
        kept: set[UUID],
        line: AttendanceItemEdit,
        actor: ActorContext,
    ) -> AttendanceExam:
        assert line.item_id is not None
        item = existing.get(line.item_id)
        if item is None or line.item_id in kept:
            raise ValidationError("Item informado não pertence ao atendimento.")
        kept.add(line.item_id)

        override_reason, override_by = item.override_reason, item.override_by
        if "pricing.read" not in actor.permissions:
            # Quem não vê valor não altera valor: o desconto já gravado é mantido.
            discount = item.discount_amount
        else:
            discount = line.discount_amount if line.discount_amount is not None else Decimal("0")
        if discount != item.discount_amount:
            if discount > 0:
                override_reason = require_discount_authority(
                    actor=actor, override_reason=line.override_reason
                )
                override_by = actor.id
            else:
                if "attendances.override_price" not in actor.permissions:
                    raise ForbiddenError("Permissão ausente: attendances.override_price")
                override_reason, override_by = None, None
        item.revise(
            quantity=line.quantity,
            discount_amount=discount,
            override_reason=override_reason,
            override_by=override_by,
            status=AttendanceExamStatus.ACTIVE,
        )
        return item


def _summary(attendance: AttendanceRecord) -> dict[str, Any]:
    return {
        "items": [
            {
                "id": str(item.id),
                "exam_code": item.exam_code,
                "quantity": item.quantity,
                "discount_amount": str(item.discount_amount),
                "total_amount": str(item.total_amount),
                "status": item.status.value,
            }
            for item in attendance.items
        ],
        "clinic_fee": str(attendance.clinic_fee),
        "grand_total": str(attendance.grand_total),
    }
