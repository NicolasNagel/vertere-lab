"""Controlled edit of a DRAFT, CONFIRMED or CANCELLED attendance
(`PATCH /attendances/{id}`). Everything can be corrected; after the draft stage a
reason is mandatory and the audit entry carries the before/after diff.

Two independent version checks exist on purpose:
1. `expected_row_version` here — compares what the *client* last saw
   against the current value, so a client editing a stale copy gets a
   clean, friendly `409 CONFLICT` (`.claude/rules/05-frontend-web-mobile.md`: "conflito
   de versão oferece recarregar, nunca sobrescreve silenciosamente"), even
   with no true concurrent request in flight.
2. `version_id_col` on `AttendanceModel` (infrastructure) — the low-level
   guard against two transactions racing on the *same* stale read, raised
   as `StaleDataError` and mapped to `409` in `api/error_handlers.py`
   (added in the cancel slice after a real race was found there).
Neither replaces the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.modules.attendances.application.attendance_items import (
    resolve_attendance_fees,
    resolve_on_call_fee,
)
from app.modules.attendances.application.closure_settlement import (
    ClosureSettlement,
    FinancialPosition,
)
from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.application.party_validation import (
    validate_clinic_veterinarian_patient,
)
from app.modules.attendances.domain.entities import AttendanceStatus, CollectionMethod, ServiceLevel
from app.modules.attendances.domain.repositories import (
    AttendanceRepository,
    ClinicFeeRuleRepository,
    OnCallFeeSettingRepository,
    UrgencyFeeSettingRepository,
)
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "attendances.update"
_FEE_INPUTS = frozenset({"service_level", "is_urgent", "clinic_id", "service_date"})


@dataclass(frozen=True, kw_only=True)
class UpdateAttendanceCommand:
    actor: ActorContext
    attendance_id: UUID
    expected_row_version: int
    clinic_id: UUID | None = None
    veterinarian_id: UUID | None = None
    patient_id: UUID | None = None
    collection_method: CollectionMethod | None = None
    service_level: ServiceLevel | None = None
    is_urgent: bool | None = None
    service_date: date | None = None
    notes: str | None = None
    reason: str | None = None


class UpdateAttendanceUseCase:
    def __init__(
        self,
        *,
        attendances: AttendanceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        veterinarian_clinics: VeterinarianClinicLinkRepository,
        patients: PatientRepository,
        on_call_fees: OnCallFeeSettingRepository,
        urgency_fee: UrgencyFeeSettingRepository,
        clinic_fee_rules: ClinicFeeRuleRepository,
        closure_settlement: ClosureSettlement,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._attendances = attendances
        self._clinics = clinics
        self._veterinarians = veterinarians
        self._veterinarian_clinics = veterinarian_clinics
        self._patients = patients
        self._on_call_fees = on_call_fees
        self._urgency_fee = urgency_fee
        self._clinic_fee_rules = clinic_fee_rules
        self._closure_settlement = closure_settlement
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdateAttendanceCommand) -> AttendanceDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        attendance = self._attendances.get_by_id(command.attendance_id)
        if attendance is None or not command.actor.can_access_clinic(attendance.clinic_id):
            raise NotFoundError("Atendimento não encontrado.")

        if command.clinic_id is not None and not command.actor.can_access_clinic(command.clinic_id):
            raise NotFoundError("Clínica não encontrada.")

        if command.expected_row_version != attendance.row_version:
            raise ConflictError(
                "O atendimento foi alterado por outra operação. Recarregue e tente novamente."
            )

        reason = (command.reason or "").strip()
        if attendance.status != AttendanceStatus.DRAFT and not reason and _has_edits(command):
            raise ValidationError("Informe o motivo da alteração.")

        if (
            command.clinic_id is not None
            or command.veterinarian_id is not None
            or command.patient_id is not None
        ):
            validate_clinic_veterinarian_patient(
                clinic_id=command.clinic_id or attendance.clinic_id,
                veterinarian_id=command.veterinarian_id or attendance.veterinarian_id,
                patient_id=command.patient_id or attendance.patient_id,
                clinics=self._clinics,
                veterinarians=self._veterinarians,
                veterinarian_clinics=self._veterinarian_clinics,
                patients=self._patients,
            )

        on_call_fee = None
        if (
            attendance.status != AttendanceStatus.DRAFT
            and command.service_level is not None
            and command.service_level != attendance.service_level
        ):
            on_call_fee = resolve_on_call_fee(
                service_level=command.service_level, on_call_fees=self._on_call_fees
            )

        position = FinancialPosition.of(attendance)
        changes = attendance.update_fields(
            clinic_id=command.clinic_id,
            veterinarian_id=command.veterinarian_id,
            patient_id=command.patient_id,
            collection_method=command.collection_method,
            service_level=command.service_level,
            is_urgent=command.is_urgent,
            service_date=command.service_date,
            notes=command.notes,
            on_call_fee=on_call_fee,
            closed_correction=True,
            now=self._clock.now(),
            updated_by=command.actor.id,
        )

        # Fees that depend on the header (level, urgency, clinic, date) are re-resolved on an
        # already-priced attendance; a rule changed later never reaches one that was not edited.
        if attendance.status != AttendanceStatus.DRAFT and _FEE_INPUTS & changes.keys():
            assert attendance.service_date is not None
            attendance.reprice_fees(
                fees=resolve_attendance_fees(
                    service_level=attendance.service_level,
                    is_urgent=attendance.is_urgent,
                    clinic_id=attendance.clinic_id,
                    service_date=attendance.service_date,
                    on_call_fees=self._on_call_fees,
                    urgency_fee=self._urgency_fee,
                    clinic_fee_rules=self._clinic_fee_rules,
                ),
                changes=changes,
                now=self._clock.now(),
                updated_by=command.actor.id,
            )

        if not changes:
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
                action="attendances.updated",
                entity_type="attendance",
                entity_id=str(attendance.id),
                before_state={field: before for field, (before, _after) in changes.items()},
                after_state={field: after for field, (_before, after) in changes.items()},
                reason=reason or None,
            )
        )

        return attendance_to_dto(attendance)


def _has_edits(command: UpdateAttendanceCommand) -> bool:
    return any(
        value is not None
        for value in (
            command.clinic_id,
            command.veterinarian_id,
            command.patient_id,
            command.collection_method,
            command.service_level,
            command.is_urgent,
            command.service_date,
            command.notes,
        )
    )
