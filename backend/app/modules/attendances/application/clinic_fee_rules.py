"""List, create and edit per-clinic fixed fees (`ClinicFeeRule`).

A rule ADDS its fixed amount to the attendance total (once per attendance and rule) while it is
active, covers the service date and its conditions (exams, attendance types) match. Editing never reaches a confirmed attendance: only a later
correction of that attendance re-resolves its fees. Lab scope only; `pricing.read` to see,
`pricing.manage` to change; mandatory reason; audit with before/after; row-version conflict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.attendances.domain.entities import ClinicFeeRule, FeeAttendanceType
from app.modules.attendances.domain.repositories import ClinicFeeRuleRepository
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
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


def _state(rule: ClinicFeeRule) -> dict[str, str | list[str] | None]:
    return {
        "clinic_id": str(rule.clinic_id),
        "name": rule.name,
        "fee_amount": str(rule.fee_amount),
        "valid_from": rule.valid_from.isoformat(),
        "valid_to": rule.valid_to.isoformat() if rule.valid_to else None,
        "is_active": str(rule.is_active),
        "exam_ids": [str(exam_id) for exam_id in rule.exam_ids],
        "attendance_types": list(rule.attendance_types),
    }


def _check_exams(exams: ExamRepository, exam_ids: tuple[UUID, ...]) -> tuple[UUID, ...]:
    unique = tuple(dict.fromkeys(exam_ids))
    if unique and len(exams.get_many_by_ids(list(unique))) != len(unique):
        raise ValidationError("Algum exame da condição não existe.")
    return unique


def _check_types(types: tuple[str, ...]) -> tuple[str, ...]:
    valid = {t.value for t in FeeAttendanceType}
    if any(value not in valid for value in types):
        raise ValidationError("Tipo de atendimento inválido na condição.")
    return tuple(dict.fromkeys(types))


def _reason(raw: str) -> str:
    reason = raw.strip()
    if not reason:
        raise ValidationError("Informe o motivo da alteração.")
    return reason


@dataclass(frozen=True, kw_only=True)
class ListClinicFeeRulesQuery:
    actor: ActorContext
    clinic_id: UUID | None = None
    include_inactive: bool = True


class ListClinicFeeRulesUseCase:
    def __init__(self, *, rules: ClinicFeeRuleRepository) -> None:
        self._rules = rules

    def execute(self, query: ListClinicFeeRulesQuery) -> list[ClinicFeeRule]:
        _require(query.actor, _READ_PERMISSION)
        return self._rules.list_rules(
            clinic_id=query.clinic_id, include_inactive=query.include_inactive
        )


@dataclass(frozen=True, kw_only=True)
class CreateClinicFeeRuleCommand:
    actor: ActorContext
    clinic_id: UUID
    name: str
    fee_amount: Decimal
    valid_from: date
    valid_to: date | None
    reason: str
    exam_ids: tuple[UUID, ...] = ()
    attendance_types: tuple[str, ...] = ()


class CreateClinicFeeRuleUseCase:
    def __init__(
        self,
        *,
        rules: ClinicFeeRuleRepository,
        clinics: ClinicRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._rules = rules
        self._clinics = clinics
        self._exams = exams
        self._audit = audit
        self._clock = clock

    def execute(self, command: CreateClinicFeeRuleCommand) -> ClinicFeeRule:
        _require(command.actor, _MANAGE_PERMISSION)
        reason = _reason(command.reason)
        if self._clinics.get_by_id(command.clinic_id) is None:
            raise NotFoundError("Clínica não encontrada.")
        exam_ids = _check_exams(self._exams, command.exam_ids)
        attendance_types = _check_types(command.attendance_types)

        now = self._clock.now()
        rule = ClinicFeeRule(
            id=uuid4(),
            clinic_id=command.clinic_id,
            name=command.name.strip(),
            fee_amount=command.fee_amount,
            valid_from=command.valid_from,
            valid_to=command.valid_to,
            exam_ids=exam_ids,
            attendance_types=attendance_types,
            created_by=command.actor.id,
            updated_by=command.actor.id,
            created_at=now,
            updated_at=now,
        )
        self._rules.add(rule)
        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="clinic_fee_rules.created",
                entity_type="clinic_fee_rule",
                entity_id=str(rule.id),
                after_state=_state(rule),
                reason=reason,
            )
        )
        return rule


@dataclass(frozen=True, kw_only=True)
class UpdateClinicFeeRuleCommand:
    actor: ActorContext
    rule_id: UUID
    name: str
    fee_amount: Decimal
    valid_from: date
    valid_to: date | None
    is_active: bool
    reason: str
    expected_row_version: int
    exam_ids: tuple[UUID, ...] = ()
    attendance_types: tuple[str, ...] = ()


class UpdateClinicFeeRuleUseCase:
    def __init__(
        self,
        *,
        rules: ClinicFeeRuleRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._rules = rules
        self._exams = exams
        self._audit = audit
        self._clock = clock

    def execute(self, command: UpdateClinicFeeRuleCommand) -> ClinicFeeRule:
        _require(command.actor, _MANAGE_PERMISSION)
        reason = _reason(command.reason)
        rule = self._rules.get_by_id(command.rule_id)
        if rule is None:
            raise NotFoundError("Taxa da clínica não encontrada.")
        if rule.row_version != command.expected_row_version:
            raise ConflictError(
                "Esta taxa foi alterada por outra pessoa. Recarregue e tente de novo."
            )

        exam_ids = _check_exams(self._exams, command.exam_ids)
        attendance_types = _check_types(command.attendance_types)
        before_state = _state(rule)
        rule.update(
            name=command.name,
            fee_amount=command.fee_amount,
            valid_from=command.valid_from,
            valid_to=command.valid_to,
            is_active=command.is_active,
            exam_ids=exam_ids,
            attendance_types=attendance_types,
            now=self._clock.now(),
            updated_by=command.actor.id,
        )
        self._rules.update(rule)
        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="clinic_fee_rules.updated",
                entity_type="clinic_fee_rule",
                entity_id=str(rule.id),
                before_state=before_state,
                after_state=_state(rule),
                reason=reason,
            )
        )
        return rule
