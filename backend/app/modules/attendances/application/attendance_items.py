"""Shared item validation + pricing snapshot for `AttendanceRecord` —
used by both `confirm_attendance.py` and `preview_attendance.py` (Fatia 2)
so a preview total can never drift from what `/confirm` would actually
charge (rule: .claude/rules/12-attendance.md, "moeda e arredondamento
centralizados em um único ponto do domínio").

Every id is revalidated here even though already checked at draft creation
(`.claude/rules/12-attendance.md`: "todo ID é revalidado no momento da
confirmação") — a preview call revalidates for the same reason: another
user may have inactivated a referenced record since the draft was created.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.attendances.application.party_validation import (
    validate_clinic_veterinarian_patient,
)
from app.modules.attendances.domain.entities import (
    AttendanceExam,
    AttendanceFees,
    AttendanceRecord,
    ExamComponentSnapshot,
    FeeKind,
    FeeLine,
    ServiceLevel,
)
from app.modules.attendances.domain.repositories import (
    ClinicFeeRuleRepository,
    OnCallFeeSettingRepository,
    UrgencyFeeSettingRepository,
)
from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import (
    ForbiddenError,
    NotFoundError,
    PriceNotAvailableError,
    ValidationError,
)

_OVERRIDE_PERMISSION = "attendances.override_price"


@dataclass(frozen=True, kw_only=True)
class AttendanceItemInput:
    exam_id: UUID
    quantity: int = 1
    discount_amount: Decimal | None = None
    override_reason: str | None = None


def resolve_on_call_fee(
    *, service_level: ServiceLevel, on_call_fees: OnCallFeeSettingRepository
) -> Decimal:
    """`NORMAL` has no configurable row — its fee is always zero
    (`domain/repositories.py::OnCallFeeSettingRepository`). For a plantão
    tier, the setting is expected to exist (seeded by migration 0031); a
    missing row is a data-integrity bug, not a user-facing 404.
    """
    if service_level == ServiceLevel.NORMAL:
        return Decimal("0")
    setting = on_call_fees.get_by_service_level(service_level)
    if setting is None:
        raise LookupError(f"Configuração de taxa de plantão ausente para {service_level.value}.")
    return setting.fee_amount


_ON_CALL_LABELS = {
    ServiceLevel.PLANTAO_NORMAL: "Plantão normal",
    ServiceLevel.PLANTAO_ESPECIAL: "Plantão especial",
}


def resolve_attendance_fees(
    *,
    service_level: ServiceLevel,
    is_urgent: bool,
    clinic_id: UUID,
    service_date: date,
    exam_ids: Iterable[UUID],
    on_call_fees: OnCallFeeSettingRepository,
    urgency_fee: UrgencyFeeSettingRepository,
    clinic_fee_rules: ClinicFeeRuleRepository,
) -> AttendanceFees:
    """Every flat per-attendance fee, resolved once and summed by the caller: plantão (by
    service level) + urgência (fixed amount, only if the attendance is urgent) + each active
    clinic rule valid on the service date whose conditions (exams, attendance types) match.
    The three ADD to each other and to the items."""
    on_call = resolve_on_call_fee(service_level=service_level, on_call_fees=on_call_fees)
    lines: list[FeeLine] = []
    if on_call > 0:
        lines.append(
            FeeLine(kind=FeeKind.PLANTAO, label=_ON_CALL_LABELS[service_level], amount=on_call)
        )

    urgency = Decimal("0")
    if is_urgent:
        setting = urgency_fee.get()
        if setting is None:
            raise LookupError("Configuração de taxa de urgência ausente.")
        urgency = setting.fee_amount
        if urgency > 0:
            lines.append(FeeLine(kind=FeeKind.URGENCIA, label="Urgência", amount=urgency))

    clinic_lines = resolve_clinic_fee_lines(
        service_level=service_level,
        is_urgent=is_urgent,
        clinic_id=clinic_id,
        service_date=service_date,
        exam_ids=exam_ids,
        clinic_fee_rules=clinic_fee_rules,
    )
    lines.extend(clinic_lines)
    clinic = sum((line.amount for line in clinic_lines), Decimal("0"))
    return AttendanceFees(on_call=on_call, urgency=urgency, clinic=clinic, lines=tuple(lines))


def resolve_clinic_fee_lines(
    *,
    service_level: ServiceLevel,
    is_urgent: bool,
    clinic_id: UUID,
    service_date: date,
    exam_ids: Iterable[UUID],
    clinic_fee_rules: ClinicFeeRuleRepository,
) -> list[FeeLine]:
    """One line per clinic rule that is active on the date AND whose conditions match; all the
    matching rules of the clinic add up."""
    exams = frozenset(exam_ids)
    return [
        FeeLine(kind=FeeKind.CLINICA, label=rule.name, amount=rule.fee_amount, rule_id=rule.id)
        for rule in clinic_fee_rules.list_applicable(clinic_id=clinic_id, service_date=service_date)
        if rule.fee_amount > 0
        and rule.matches(exam_ids=exams, service_level=service_level, is_urgent=is_urgent)
    ]


def _component_snapshot(exam: Exam, exams: ExamRepository) -> tuple[ExamComponentSnapshot, ...]:
    """Freeze a panel's composition now; plain exams have none. Order follows the panel."""
    if not exam.is_panel:
        return ()
    by_id = {
        component.id: component for component in exams.get_many_by_ids(list(exam.component_ids))
    }
    return tuple(
        ExamComponentSnapshot(code=str(by_id[component_id].code), name=by_id[component_id].name)
        for component_id in exam.component_ids
        if component_id in by_id
    )


def validate_and_snapshot_items(
    *,
    attendance: AttendanceRecord,
    items: list[AttendanceItemInput],
    actor: ActorContext,
    clinics: ClinicRepository,
    veterinarians: VeterinarianRepository,
    veterinarian_clinics: VeterinarianClinicLinkRepository,
    patients: PatientRepository,
    exams: ExamRepository,
) -> list[AttendanceExam]:
    if not items:
        raise ValidationError("Confirmação exige ao menos um item de exame.")
    if attendance.service_date is None:
        raise ValidationError("Data do atendimento é obrigatória para confirmar.")

    validate_clinic_veterinarian_patient(
        clinic_id=attendance.clinic_id,
        veterinarian_id=attendance.veterinarian_id,
        patient_id=attendance.patient_id,
        clinics=clinics,
        veterinarians=veterinarians,
        veterinarian_clinics=veterinarian_clinics,
        patients=patients,
    )

    return [
        snapshot_item(attendance=attendance, item_input=item_input, actor=actor, exams=exams)
        for item_input in items
    ]


def require_discount_authority(*, actor: ActorContext, override_reason: str | None) -> str:
    """A discount needs `attendances.override_price` and a stated reason."""
    if _OVERRIDE_PERMISSION not in actor.permissions:
        raise ForbiddenError(f"Permissão ausente: {_OVERRIDE_PERMISSION}")
    if not override_reason or not override_reason.strip():
        raise ValidationError("Override de preço exige motivo.")
    return override_reason.strip()


def snapshot_item(
    *,
    attendance: AttendanceRecord,
    item_input: AttendanceItemInput,
    actor: ActorContext,
    exams: ExamRepository,
) -> AttendanceExam:
    """Price one exam on the attendance's service date and freeze it as a snapshot.
    Also used when an exam is added after confirmation — the price is the one valid
    on the service date, not today's."""
    assert attendance.service_date is not None
    exam = exams.get_by_id(item_input.exam_id)
    if exam is None:
        raise NotFoundError("Exame não encontrado.")
    if exam.status != ExamStatus.ACTIVE:
        raise ValidationError("Exame não está ativo.")
    if not exam.has_price_on(attendance.service_date):
        raise PriceNotAvailableError("Exame sem preço vigente na data do atendimento.")

    discount_amount = item_input.discount_amount or Decimal("0")
    override_reason: str | None = None
    override_by: UUID | None = None
    if discount_amount > 0:
        override_reason = require_discount_authority(
            actor=actor, override_reason=item_input.override_reason
        )
        override_by = actor.id

    return AttendanceExam(
        id=uuid4(),
        attendance_id=attendance.id,
        exam_id=exam.id,
        exam_code=str(exam.code),
        exam_name=exam.name,
        price_base=exam.price_base,
        components=_component_snapshot(exam, exams),
        quantity=item_input.quantity,
        discount_amount=discount_amount,
        # O adicional de plantão não é mais por item — é uma taxa fixa por
        # atendimento inteiro, somada em `compute_attendance_totals`.
        surcharge_amount=Decimal("0"),
        override_reason=override_reason,
        override_by=override_by,
    )
