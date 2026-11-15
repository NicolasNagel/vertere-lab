"""Módulo de Taxas: plantão + urgência + taxas por clínica somam ao total do atendimento."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.attendances.application.clinic_fee_rules import (
    CreateClinicFeeRuleCommand,
    CreateClinicFeeRuleUseCase,
    ListClinicFeeRulesQuery,
    ListClinicFeeRulesUseCase,
    UpdateClinicFeeRuleCommand,
    UpdateClinicFeeRuleUseCase,
)
from app.modules.attendances.application.urgency_fee_setting import (
    GetUrgencyFeeSettingQuery,
    GetUrgencyFeeSettingUseCase,
    UpdateUrgencyFeeSettingCommand,
    UpdateUrgencyFeeSettingUseCase,
)
from app.modules.attendances.domain.entities import ClinicFeeRule, ServiceLevel
from app.modules.attendances.domain.fee_schedule import FeeSchedule
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from tests.attendances.fakes import FakeClinicFeeRuleRepository, FakeClock
from tests.attendances.test_attendance_use_cases import (
    _CLINIC_ID,
    _NOW,
    _actor,
    _command,
    _confirm_command,
    _ConfirmFixture,
    _preview_command,
    _update_command,
)

_MANAGE = frozenset({"pricing.manage", "pricing.read"})


def _rule(**overrides: object) -> ClinicFeeRule:
    values: dict[str, object] = {
        "id": uuid4(),
        "clinic_id": _CLINIC_ID,
        "name": "Taxa de coleta",
        "fee_amount": Decimal("5.00"),
        "valid_from": date(2026, 1, 1),
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    values.update(overrides)
    return ClinicFeeRule(**values)  # type: ignore[arg-type]


def _lab_actor(permissions: frozenset[str] = _MANAGE):  # type: ignore[no-untyped-def]
    return _actor(permissions=permissions)


def test_plantao_urgency_and_clinic_fee_add_up_with_the_items() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    fixture.urgency_fee.get().fee_amount = Decimal("30.00")  # type: ignore[union-attr]
    fixture.clinic_fee_rules.add(_rule(name="Taxa A", fee_amount=Decimal("5.00")))
    fixture.clinic_fee_rules.add(_rule(name="Taxa B", fee_amount=Decimal("2.50")))

    draft = fixture.use_case().execute(
        _command(service_level=ServiceLevel.PLANTAO_NORMAL, is_urgent=True)
    )
    preview = fixture.preview_use_case().execute(_preview_command(attendance_id=draft.id))
    confirmed = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    # 2 x 100 de exames + 100 de plantão + 30 de urgência + 7,50 de taxas da clínica.
    assert confirmed.grand_total == Decimal("337.50")
    assert (confirmed.on_call_fee, confirmed.urgency_fee, confirmed.clinic_fee) == (
        Decimal("100.00"),
        Decimal("30.00"),
        Decimal("7.50"),
    )
    assert preview.grand_total == confirmed.grand_total  # a prévia cobra o que a confirmação cobra
    assert [(line.kind, line.label, line.amount) for line in confirmed.fee_lines] == [
        ("PLANTAO", "Plantão normal", Decimal("100.00")),
        ("URGENCIA", "Urgência", Decimal("30.00")),
        ("CLINICA", "Taxa A", Decimal("5.00")),
        ("CLINICA", "Taxa B", Decimal("2.50")),
    ]


def test_clinic_rule_outside_validity_or_inactive_or_from_other_clinic_is_not_charged() -> None:
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    fixture.clinic_fee_rules.add(_rule(valid_from=date(2026, 2, 1)))  # ainda não vale
    fixture.clinic_fee_rules.add(
        _rule(valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31))
    )  # já encerrou
    fixture.clinic_fee_rules.add(_rule(is_active=False))
    fixture.clinic_fee_rules.add(_rule(clinic_id=uuid4()))

    draft = fixture.use_case().execute(_command())
    confirmed = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))

    assert (confirmed.clinic_fee, confirmed.fee_lines) == (Decimal("0"), ())
    assert confirmed.grand_total == Decimal("200.00")


def test_changing_a_rule_later_does_not_touch_a_confirmed_attendance_but_a_correction_does() -> (
    None
):
    fixture = _ConfirmFixture(exam_price=Decimal("100.00"))
    rule = _rule(fee_amount=Decimal("5.00"))
    fixture.clinic_fee_rules.add(rule)
    draft = fixture.use_case().execute(_command())
    confirmed = fixture.confirm_use_case().execute(_confirm_command(attendance_id=draft.id))
    assert confirmed.grand_total == Decimal("205.00")

    rule.update(
        name=rule.name,
        fee_amount=Decimal("9.00"),
        valid_from=rule.valid_from,
        valid_to=None,
        is_active=True,
        now=_NOW,
        updated_by=None,
    )
    still = fixture.attendances.get_by_id(confirmed.id)
    assert still is not None and still.grand_total == Decimal("205.00")  # snapshot

    # Editar uma nota não reprecifica; marcar urgente reprecifica com a regra vigente.
    fixture.urgency_fee.get().fee_amount = Decimal("20.00")  # type: ignore[union-attr]
    noted = fixture.update_use_case().execute(
        _update_command(
            attendance_id=confirmed.id,
            expected_row_version=confirmed.row_version,
            notes="obs",
            reason="Observação",
        )
    )
    assert noted.grand_total == Decimal("205.00")

    urgent = fixture.update_use_case().execute(
        _update_command(
            attendance_id=confirmed.id,
            expected_row_version=noted.row_version,
            is_urgent=True,
            reason="Era urgente",
        )
    )
    assert (urgent.urgency_fee, urgent.clinic_fee) == (Decimal("20.00"), Decimal("9.00"))
    assert urgent.grand_total == Decimal("229.00")
    entry = fixture.audit.entries[-1]
    assert entry.before_state is not None and entry.after_state is not None
    assert entry.before_state["grand_total"] == "205.00"
    assert entry.after_state["grand_total"] == "229.00"
    assert entry.after_state["is_urgent"] == "True"
    assert entry.after_state["urgency_fee"] == "20.00"
    assert fixture.closure_settlement.calls == []  # não estava fechado

    # Mudar a data para fora da vigência tira a taxa da clínica.
    rule.update(
        name=rule.name,
        fee_amount=Decimal("9.00"),
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 1, 31),
        is_active=True,
        now=_NOW,
        updated_by=None,
    )
    moved = fixture.update_use_case().execute(
        _update_command(
            attendance_id=confirmed.id,
            expected_row_version=urgent.row_version,
            service_date=date(2026, 3, 10),
            reason="Data errada",
        )
    )
    assert (moved.clinic_fee, moved.grand_total) == (Decimal("0"), Decimal("220.00"))


def test_urgency_fee_setting_needs_permission_reason_version_and_is_audited() -> None:
    fixture = _ConfirmFixture()
    repo = fixture.urgency_fee
    audit = fixture.audit
    use_case = UpdateUrgencyFeeSettingUseCase(urgency_fee=repo, audit=audit, clock=FakeClock(_NOW))

    def command(**overrides: object) -> UpdateUrgencyFeeSettingCommand:
        values: dict[str, object] = {
            "actor": _lab_actor(),
            "fee_amount": Decimal("45.00"),
            "schedule": FeeSchedule(weekdays=(5, 6), start_time=time(8), end_time=time(12, 30)),
            "reason": "Reajuste anual",
            "expected_row_version": 1,
        }
        values.update(overrides)
        return UpdateUrgencyFeeSettingCommand(**values)  # type: ignore[arg-type]

    with pytest.raises(ForbiddenError):
        use_case.execute(command(actor=_lab_actor(frozenset({"pricing.read"}))))
    with pytest.raises(ValidationError):
        use_case.execute(command(reason="  "))
    with pytest.raises(ValidationError):
        use_case.execute(command(fee_amount=Decimal("-1")))
    with pytest.raises(ConflictError):
        use_case.execute(command(expected_row_version=9))

    result = use_case.execute(command())
    assert result.fee_amount == Decimal("45.00")
    entry = audit.entries[-1]
    assert entry.action == "urgency_fee_settings.updated"
    assert entry.reason == "Reajuste anual"
    assert entry.before_state == {
        "fee_amount": "0.00",
        "schedule_label": "",
        "weekdays": [],
        "start_time": None,
        "end_time": None,
    }
    assert entry.after_state == {
        "fee_amount": "45.00",
        "schedule_label": "Fim de semana · 08h às 12:30",
        "weekdays": [5, 6],
        "start_time": "08:00",
        "end_time": "12:30",
    }

    getter = GetUrgencyFeeSettingUseCase(urgency_fee=repo)
    with pytest.raises(ForbiddenError):
        getter.execute(GetUrgencyFeeSettingQuery(actor=_lab_actor(frozenset())))
    assert getter.execute(GetUrgencyFeeSettingQuery(actor=_lab_actor())).fee_amount == Decimal(
        "45.00"
    )


def test_clinic_fee_rules_crud_is_gated_audited_and_validated() -> None:
    fixture = _ConfirmFixture()
    rules = fixture.clinic_fee_rules
    create = CreateClinicFeeRuleUseCase(
        rules=rules, clinics=fixture.clinics, audit=fixture.audit, clock=FakeClock(_NOW)
    )
    update = UpdateClinicFeeRuleUseCase(rules=rules, audit=fixture.audit, clock=FakeClock(_NOW))

    def new(**overrides: object) -> CreateClinicFeeRuleCommand:
        values: dict[str, object] = {
            "actor": _lab_actor(),
            "clinic_id": _CLINIC_ID,
            "name": "Bicho Urbano",
            "fee_amount": Decimal("5.00"),
            "valid_from": date(2026, 1, 1),
            "valid_to": None,
            "reason": "Acordo comercial",
        }
        values.update(overrides)
        return CreateClinicFeeRuleCommand(**values)  # type: ignore[arg-type]

    with pytest.raises(ForbiddenError):
        create.execute(new(actor=_lab_actor(frozenset({"pricing.read"}))))
    with pytest.raises(ValidationError):
        create.execute(new(reason=""))
    with pytest.raises(ValidationError):
        create.execute(new(valid_to=date(2025, 1, 1)))
    with pytest.raises(ValidationError):
        create.execute(new(fee_amount=Decimal("-1")))
    with pytest.raises(NotFoundError):
        create.execute(new(clinic_id=uuid4()))

    created = create.execute(new())
    assert fixture.audit.entries[-1].action == "clinic_fee_rules.created"
    assert fixture.audit.entries[-1].reason == "Acordo comercial"

    def change(**overrides: object) -> UpdateClinicFeeRuleCommand:
        values: dict[str, object] = {
            "actor": _lab_actor(),
            "rule_id": created.id,
            "name": "Bicho Urbano",
            "fee_amount": Decimal("6.00"),
            "valid_from": date(2026, 1, 1),
            "valid_to": None,
            "is_active": True,
            "reason": "Reajuste",
            "expected_row_version": 1,
        }
        values.update(overrides)
        return UpdateClinicFeeRuleCommand(**values)  # type: ignore[arg-type]

    with pytest.raises(ConflictError):
        update.execute(change(expected_row_version=3))
    with pytest.raises(NotFoundError):
        update.execute(change(rule_id=uuid4()))
    with pytest.raises(ValidationError):
        update.execute(change(reason=" "))

    updated = update.execute(change(is_active=False))
    assert (updated.fee_amount, updated.is_active) == (Decimal("6.00"), False)
    entry = fixture.audit.entries[-1]
    assert entry.action == "clinic_fee_rules.updated"
    assert entry.before_state is not None and entry.after_state is not None
    assert (entry.before_state["fee_amount"], entry.after_state["fee_amount"]) == ("5.00", "6.00")
    assert (entry.before_state["is_active"], entry.after_state["is_active"]) == ("True", "False")

    lister = ListClinicFeeRulesUseCase(rules=FakeClinicFeeRuleRepository([created]))
    with pytest.raises(ForbiddenError):
        lister.execute(ListClinicFeeRulesQuery(actor=_lab_actor(frozenset())))
    assert len(lister.execute(ListClinicFeeRulesQuery(actor=_lab_actor()))) == 1
