from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarian_clinics.application.set_veterinarian_clinics import (
    SetVeterinarianClinicsCommand,
    SetVeterinarianClinicsUseCase,
)
from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink
from app.modules.veterinarian_clinics.domain.errors import LastClinicLinkRequiredError
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus
from app.modules.veterinarians.domain.value_objects import Crmv
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from tests.veterinarian_clinics.fakes import (
    FakeAuditLogWriter,
    FakeClinicRepository,
    FakeClock,
    FakeVeterinarianClinicLinkRepository,
    FakeVeterinarianRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_MANAGER = frozenset({"veterinarians.manage"})


class _Env:
    def __init__(self, *, is_autonomous: bool = False) -> None:
        self.veterinarians = FakeVeterinarianRepository()
        self.clinics = FakeClinicRepository()
        self.links = FakeVeterinarianClinicLinkRepository()
        self.audit = FakeAuditLogWriter()
        self.veterinarian = Veterinarian(
            id=uuid4(),
            name="Dra. Fabianna Garcia",
            crmv=Crmv(f"CRMV-SC {uuid4().hex[:5]}"),
            is_autonomous=is_autonomous,
            status=VeterinarianStatus.ACTIVE,
            created_at=_NOW,
            updated_at=_NOW,
        )
        self.veterinarians.add(self.veterinarian)

    def clinic(self, *, status: ClinicStatus = ClinicStatus.ACTIVE) -> UUID:
        clinic = Clinic(id=uuid4(), name="Clínica", status=status, created_at=_NOW, updated_at=_NOW)
        self.clinics.add(clinic)
        return clinic.id

    def link(self, clinic_id: UUID, *, primary: bool = False) -> None:
        self.links.add(
            VeterinarianClinicLink(
                id=uuid4(),
                veterinarian_id=self.veterinarian.id,
                clinic_id=clinic_id,
                primary_clinic=primary,
                created_by=None,
                created_at=_NOW,
            )
        )

    def run(
        self,
        *,
        add: tuple[UUID, ...] = (),
        remove: tuple[UUID, ...] = (),
        primary: UUID | None = None,
        reason: str = "Ajuste de carteira",
        row_version: int | None = None,
        permissions: frozenset[str] = _MANAGER,
    ) -> None:
        SetVeterinarianClinicsUseCase(
            veterinarians=self.veterinarians,
            clinics=self.clinics,
            links=self.links,
            audit=self.audit,
            clock=FakeClock(_NOW),
        ).execute(
            SetVeterinarianClinicsCommand(
                actor=AuthenticatedUserDTO(
                    user_id=uuid4(),
                    email="user@vertere.local",
                    full_name="User",
                    role_id=uuid4(),
                    role_name="LAB_ADMIN",
                    permissions=permissions,
                ),
                veterinarian_id=self.veterinarian.id,
                add_clinic_ids=add,
                remove_clinic_ids=remove,
                primary_clinic_id=primary,
                expected_row_version=(
                    self.veterinarian.row_version if row_version is None else row_version
                ),
                reason=reason,
            )
        )

    def linked_ids(self) -> set[UUID]:
        return {link.clinic_id for link in self.links.list_by_veterinarian(self.veterinarian.id)}

    def primary_ids(self) -> list[UUID]:
        return [
            link.clinic_id
            for link in self.links.list_by_veterinarian(self.veterinarian.id)
            if link.primary_clinic
        ]


def test_adds_and_removes_many_clinics_in_one_call_with_a_single_audit_entry() -> None:
    env = _Env()
    kept, dropped = env.clinic(), env.clinic()
    env.link(kept, primary=True)
    env.link(dropped)
    new = [env.clinic() for _ in range(120)]

    env.run(add=tuple(new), remove=(dropped,))

    assert env.linked_ids() == {kept, *new}
    assert env.primary_ids() == [kept]
    assert len(env.audit.entries) == 1
    entry = env.audit.entries[0]
    assert entry.action == "veterinarian_clinics.batch_updated"
    assert entry.reason == "Ajuste de carteira"
    assert entry.before_state is not None and entry.before_state["clinic_count"] == 2
    assert entry.after_state is not None and entry.after_state["clinic_count"] == 121


def test_primary_can_move_to_a_clinic_added_in_the_same_call() -> None:
    env = _Env()
    old = env.clinic()
    env.link(old, primary=True)
    new = env.clinic()

    env.run(add=(new,), primary=new)

    assert env.primary_ids() == [new]


def test_removing_the_primary_promotes_a_remaining_clinic() -> None:
    env = _Env()
    primary, other = env.clinic(), env.clinic()
    env.link(primary, primary=True)
    env.link(other)

    env.run(remove=(primary,))

    assert env.primary_ids() == [other]


def test_bumps_row_version_and_is_noop_when_nothing_changes() -> None:
    env = _Env()
    clinic = env.clinic()
    env.link(clinic, primary=True)
    version = env.veterinarian.row_version

    env.run(add=(clinic,), remove=())

    assert env.audit.entries == []
    assert env.veterinarian.row_version == version


def test_non_autonomous_cannot_end_up_without_clinics_and_nothing_is_applied() -> None:
    env = _Env()
    only = env.clinic()
    env.link(only, primary=True)

    with pytest.raises(LastClinicLinkRequiredError):
        env.run(remove=(only,))

    assert env.linked_ids() == {only}
    assert env.audit.entries == []


def test_autonomous_may_end_up_without_clinics() -> None:
    env = _Env(is_autonomous=True)
    only = env.clinic()
    env.link(only, primary=True)

    env.run(remove=(only,))

    assert env.linked_ids() == set()


def test_requires_a_reason() -> None:
    env = _Env()
    with pytest.raises(ValidationError):
        env.run(add=(env.clinic(),), reason="   ")


def test_requires_manage_permission() -> None:
    env = _Env()
    with pytest.raises(ForbiddenError):
        env.run(add=(env.clinic(),), permissions=frozenset({"veterinarians.read"}))


def test_stale_row_version_is_a_conflict_and_changes_nothing() -> None:
    env = _Env()
    clinic = env.clinic()
    with pytest.raises(ConflictError):
        env.run(add=(clinic,), row_version=env.veterinarian.row_version + 3)
    assert env.linked_ids() == set()


def test_rejects_overlap_duplicates_unknown_inactive_and_foreign_primary() -> None:
    env = _Env()
    existing = env.clinic()
    env.link(existing, primary=True)
    clinic = env.clinic()
    inactive = env.clinic(status=ClinicStatus.INACTIVE)

    with pytest.raises(ValidationError):
        env.run(add=(clinic,), remove=(clinic,))
    with pytest.raises(ValidationError):
        env.run(add=(clinic, clinic))
    with pytest.raises(NotFoundError):
        env.run(add=(uuid4(),))
    with pytest.raises(ValidationError):
        env.run(add=(inactive,))
    with pytest.raises(ValidationError):
        env.run(primary=clinic)

    assert env.linked_ids() == {existing}
    assert env.audit.entries == []


def test_rejects_more_than_the_per_request_limit() -> None:
    env = _Env()
    existing = env.clinic()
    env.link(existing, primary=True)
    too_many = tuple(uuid4() for _ in range(501))
    with pytest.raises(ValidationError):
        env.run(add=too_many)
