"""Cancel a DRAFT or CONFIRMED attendance — Fatia 3 of the attendance plan
checkpoint. Cancellation requires a reason
(`.claude/rules/12-attendance.md`: "cancelamento exige motivo") and is
rejected once the attendance belongs to a closure
(`AttendanceAlreadyClosedError`, enforced in `AttendanceRecord.cancel()`).

No `Idempotency-Key` here: unlike `/confirm`, a retried cancel of an
already-cancelled attendance fails safely with `409
INVALID_STATE_TRANSITION` instead of silently duplicating an effect — there
is no financial state to duplicate, only a status flip guarded by the
domain's own state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.domain.repositories import AttendanceRepository
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "attendances.cancel"


@dataclass(frozen=True, kw_only=True)
class CancelAttendanceCommand:
    actor: ActorContext
    attendance_id: UUID
    reason: str


class CancelAttendanceUseCase:
    def __init__(
        self,
        *,
        attendances: AttendanceRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._attendances = attendances
        self._audit = audit
        self._clock = clock

    def execute(self, command: CancelAttendanceCommand) -> AttendanceDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        attendance = self._attendances.get_by_id(command.attendance_id)
        if attendance is None:
            raise NotFoundError("Atendimento não encontrado.")

        reason = command.reason.strip()
        if not reason:
            raise ValidationError("Cancelamento exige motivo.")

        before_state = {"status": attendance.status.value}

        attendance.cancel(reason=reason, now=self._clock.now(), cancelled_by=command.actor.id)
        self._attendances.update(attendance)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="attendances.cancelled",
                entity_type="attendance",
                entity_id=str(attendance.id),
                before_state=before_state,
                after_state={"status": attendance.status.value},
                reason=reason,
            )
        )

        return attendance_to_dto(attendance)
