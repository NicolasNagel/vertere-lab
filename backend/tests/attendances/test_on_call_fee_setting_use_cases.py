"""Unit tests for the configurable on-call fee settings use cases — Fatia 2
of the "Exames & Preços" mockup-fidelity plan
(`dentro-da-pasta-assets-enchanted-narwhal.md`). Reverts the "não
configurável" `ON_CALL_FEES` constant into a persisted, audited,
permission-gated setting.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.attendances.application.get_on_call_fee_settings import (
    GetOnCallFeeSettingsQuery,
    GetOnCallFeeSettingsUseCase,
)
from app.modules.attendances.application.update_on_call_fee_setting import (
    UpdateOnCallFeeSettingCommand,
    UpdateOnCallFeeSettingUseCase,
)
from app.modules.attendances.domain.entities import ServiceLevel
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from tests.attendances.fakes import (
    FakeAuditLogWriter,
    FakeClock,
    FakeOnCallFeeSettingRepository,
    make_on_call_fee_setting,
)

_NOW = datetime(2026, 2, 1, tzinfo=UTC)


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="finance@vertere.local",
        full_name="Finance",
        role_id=uuid4(),
        role_name="FINANCE",
        permissions=permissions,
    )


def _update_command(
    *, permissions: frozenset[str] = frozenset({"pricing.manage"}), **overrides: object
) -> UpdateOnCallFeeSettingCommand:
    values: dict[str, object] = {
        "actor": _actor(permissions=permissions),
        "service_level": ServiceLevel.PLANTAO_NORMAL,
        "fee_amount": Decimal("120.00"),
        "schedule_label": "Seg-Sáb - 19h às 07h",
        "expected_row_version": 1,
    }
    values.update(overrides)
    return UpdateOnCallFeeSettingCommand(**values)  # type: ignore[arg-type]


def test_get_on_call_fee_settings_returns_both_tiers_and_checks_permission() -> None:
    use_case = GetOnCallFeeSettingsUseCase(on_call_fees=FakeOnCallFeeSettingRepository())

    result = use_case.execute(
        GetOnCallFeeSettingsQuery(actor=_actor(permissions=frozenset({"pricing.read"})))
    )
    assert {setting.service_level for setting in result} == {
        ServiceLevel.PLANTAO_NORMAL,
        ServiceLevel.PLANTAO_ESPECIAL,
    }
    with pytest.raises(ForbiddenError):
        use_case.execute(GetOnCallFeeSettingsQuery(actor=_actor(permissions=frozenset())))


def test_update_on_call_fee_setting_persists_audits_and_rejects_invalid_requests() -> None:
    repo = FakeOnCallFeeSettingRepository()
    audit = FakeAuditLogWriter()
    use_case = UpdateOnCallFeeSettingUseCase(on_call_fees=repo, audit=audit, clock=FakeClock(_NOW))

    result = use_case.execute(_update_command())

    assert result.fee_amount == Decimal("120.00")
    assert result.schedule_label == "Seg-Sáb - 19h às 07h"
    assert result.row_version == 1  # o fake não simula o incremento do banco
    stored = repo.get_by_service_level(ServiceLevel.PLANTAO_NORMAL)
    assert stored is not None
    assert stored.fee_amount == Decimal("120.00")
    assert [(entry.action, entry.before_state, entry.after_state) for entry in audit.entries] == [
        (
            "on_call_fee_settings.updated",
            {"fee_amount": "100.00", "schedule_label": ""},
            {"fee_amount": "120.00", "schedule_label": "Seg-Sáb - 19h às 07h"},
        )
    ]

    with pytest.raises(ForbiddenError):
        use_case.execute(_update_command(permissions=frozenset({"pricing.read"})))
    with pytest.raises(ValidationError):  # atendimento normal não tem taxa de plantão
        use_case.execute(_update_command(service_level=ServiceLevel.NORMAL))

    empty = UpdateOnCallFeeSettingUseCase(
        on_call_fees=FakeOnCallFeeSettingRepository(settings=[]),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )
    with pytest.raises(NotFoundError):
        empty.execute(_update_command())

    stale = UpdateOnCallFeeSettingUseCase(
        on_call_fees=FakeOnCallFeeSettingRepository(
            settings=[
                make_on_call_fee_setting(
                    service_level=ServiceLevel.PLANTAO_NORMAL,
                    fee_amount=Decimal("100.00"),
                    row_version=3,
                )
            ]
        ),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )
    with pytest.raises(ConflictError):
        stale.execute(_update_command(expected_row_version=1))
