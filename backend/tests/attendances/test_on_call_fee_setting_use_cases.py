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


def test_get_on_call_fee_settings_returns_both_tiers() -> None:
    repo = FakeOnCallFeeSettingRepository()
    use_case = GetOnCallFeeSettingsUseCase(on_call_fees=repo)

    result = use_case.execute(
        GetOnCallFeeSettingsQuery(actor=_actor(permissions=frozenset({"pricing.read"})))
    )

    service_levels = {setting.service_level for setting in result}
    assert service_levels == {ServiceLevel.PLANTAO_NORMAL, ServiceLevel.PLANTAO_ESPECIAL}


def test_get_on_call_fee_settings_without_permission_is_forbidden() -> None:
    use_case = GetOnCallFeeSettingsUseCase(on_call_fees=FakeOnCallFeeSettingRepository())

    with pytest.raises(ForbiddenError):
        use_case.execute(GetOnCallFeeSettingsQuery(actor=_actor(permissions=frozenset())))


def test_update_on_call_fee_setting_succeeds_and_records_audit() -> None:
    repo = FakeOnCallFeeSettingRepository()
    audit = FakeAuditLogWriter()
    use_case = UpdateOnCallFeeSettingUseCase(on_call_fees=repo, audit=audit, clock=FakeClock(_NOW))
    actor = _actor(permissions=frozenset({"pricing.manage"}))

    result = use_case.execute(
        UpdateOnCallFeeSettingCommand(
            actor=actor,
            service_level=ServiceLevel.PLANTAO_NORMAL,
            fee_amount=Decimal("120.00"),
            schedule_label="Seg-Sáb - 19h às 07h",
            expected_row_version=1,
        )
    )

    assert result.fee_amount == Decimal("120.00")
    assert result.schedule_label == "Seg-Sáb - 19h às 07h"
    assert result.row_version == 1  # fake repo does not simulate the DB version bump

    stored = repo.get_by_service_level(ServiceLevel.PLANTAO_NORMAL)
    assert stored is not None
    assert stored.fee_amount == Decimal("120.00")

    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry.action == "on_call_fee_settings.updated"
    assert entry.before_state == {"fee_amount": "100.00", "schedule_label": ""}
    assert entry.after_state == {"fee_amount": "120.00", "schedule_label": "Seg-Sáb - 19h às 07h"}


def test_update_on_call_fee_setting_without_permission_is_forbidden() -> None:
    use_case = UpdateOnCallFeeSettingUseCase(
        on_call_fees=FakeOnCallFeeSettingRepository(),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(
            UpdateOnCallFeeSettingCommand(
                actor=_actor(permissions=frozenset({"pricing.read"})),
                service_level=ServiceLevel.PLANTAO_NORMAL,
                fee_amount=Decimal("120.00"),
                schedule_label="",
                expected_row_version=1,
            )
        )


def test_update_on_call_fee_setting_rejects_normal_service_level() -> None:
    use_case = UpdateOnCallFeeSettingUseCase(
        on_call_fees=FakeOnCallFeeSettingRepository(),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )

    with pytest.raises(ValidationError):
        use_case.execute(
            UpdateOnCallFeeSettingCommand(
                actor=_actor(permissions=frozenset({"pricing.manage"})),
                service_level=ServiceLevel.NORMAL,
                fee_amount=Decimal("10.00"),
                schedule_label="",
                expected_row_version=1,
            )
        )


def test_update_on_call_fee_setting_unknown_setting_is_not_found() -> None:
    use_case = UpdateOnCallFeeSettingUseCase(
        on_call_fees=FakeOnCallFeeSettingRepository(settings=[]),
        audit=FakeAuditLogWriter(),
        clock=FakeClock(_NOW),
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            UpdateOnCallFeeSettingCommand(
                actor=_actor(permissions=frozenset({"pricing.manage"})),
                service_level=ServiceLevel.PLANTAO_NORMAL,
                fee_amount=Decimal("10.00"),
                schedule_label="",
                expected_row_version=1,
            )
        )


def test_update_on_call_fee_setting_stale_version_is_conflict() -> None:
    repo = FakeOnCallFeeSettingRepository(
        settings=[
            make_on_call_fee_setting(
                service_level=ServiceLevel.PLANTAO_NORMAL,
                fee_amount=Decimal("100.00"),
                row_version=3,
            )
        ]
    )
    use_case = UpdateOnCallFeeSettingUseCase(
        on_call_fees=repo, audit=FakeAuditLogWriter(), clock=FakeClock(_NOW)
    )

    with pytest.raises(ConflictError):
        use_case.execute(
            UpdateOnCallFeeSettingCommand(
                actor=_actor(permissions=frozenset({"pricing.manage"})),
                service_level=ServiceLevel.PLANTAO_NORMAL,
                fee_amount=Decimal("10.00"),
                schedule_label="",
                expected_row_version=1,
            )
        )
