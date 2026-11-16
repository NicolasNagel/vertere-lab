from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.clinics.domain.entities import Clinic, ClinicStatus
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.veterinarian_clinics.application.link_veterinarian_to_clinic import (
    LinkVeterinarianToClinicCommand,
    LinkVeterinarianToClinicUseCase,
)
from app.modules.veterinarian_clinics.application.list_clinics_for_veterinarian import (
    ListClinicsForVeterinarianQuery,
    ListClinicsForVeterinarianUseCase,
)
from app.modules.veterinarian_clinics.application.list_veterinarians_for_clinic import (
    ListVeterinariansForClinicQuery,
    ListVeterinariansForClinicUseCase,
)
from app.modules.veterinarian_clinics.application.unlink_veterinarian_from_clinic import (
    UnlinkVeterinarianFromClinicCommand,
    UnlinkVeterinarianFromClinicUseCase,
)
from app.modules.veterinarian_clinics.domain.errors import LastClinicLinkRequiredError
from app.modules.veterinarians.domain.entities import Veterinarian, VeterinarianStatus
from app.modules.veterinarians.domain.value_objects import Crmv
from app.shared.domain.errors import ForbiddenError, NotFoundError
from tests.veterinarian_clinics.fakes import (
    FakeAuditLogWriter,
    FakeClinicRepository,
    FakeClock,
    FakeVeterinarianClinicLinkRepository,
    FakeVeterinarianRepository,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _actor(*, permissions: frozenset[str]) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="user@vertere.local",
        full_name="User",
        role_id=uuid4(),
        role_name="RECEPTION",
        permissions=permissions,
    )


def _veterinarian(*, is_autonomous: bool = False) -> Veterinarian:
    return Veterinarian(
        id=uuid4(),
        name="Dra. Fabianna Garcia",
        crmv=Crmv(f"CRMV-SC {uuid4().hex[:5]}"),
        is_autonomous=is_autonomous,
        status=VeterinarianStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _clinic(*, name: str = "Schweitzer") -> Clinic:
    return Clinic(
        id=uuid4(),
        name=name,
        status=ClinicStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _setup() -> tuple[
    FakeVeterinarianRepository,
    FakeClinicRepository,
    FakeVeterinarianClinicLinkRepository,
    FakeAuditLogWriter,
]:
    return (
        FakeVeterinarianRepository(),
        FakeClinicRepository(),
        FakeVeterinarianClinicLinkRepository(),
        FakeAuditLogWriter(),
    )


_MANAGER = frozenset({"veterinarians.manage"})


def _link_use_case(
    veterinarians: FakeVeterinarianRepository,
    clinics: FakeClinicRepository,
    links: FakeVeterinarianClinicLinkRepository,
    audit: FakeAuditLogWriter,
) -> LinkVeterinarianToClinicUseCase:
    return LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    )


def _link_command(
    veterinarian_id: UUID,
    clinic_id: UUID,
    *,
    primary: bool = False,
    permissions: frozenset[str] = _MANAGER,
) -> LinkVeterinarianToClinicCommand:
    return LinkVeterinarianToClinicCommand(
        actor=_actor(permissions=permissions),
        veterinarian_id=veterinarian_id,
        clinic_id=clinic_id,
        primary_clinic=primary,
    )


def _clinic_actor(
    *, clinic_ids: frozenset[UUID], permissions: frozenset[str]
) -> AuthenticatedUserDTO:
    return AuthenticatedUserDTO(
        user_id=uuid4(),
        email="clinic@vertere.local",
        full_name="Clinic User",
        role_id=uuid4(),
        role_name="CLINIC_STAFF",
        role_scope="CLINIC",
        permissions=permissions,
        clinic_ids=clinic_ids,
    )


def test_link_veterinarian_to_clinic_enforces_rules_idempotency_and_single_primary() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian()
    clinic_a = _clinic(name="Schweitzer")
    clinic_b = _clinic(name="Bicho Urbano")
    veterinarians.add(veterinarian)
    clinics.add(clinic_a)
    clinics.add(clinic_b)
    link = _link_use_case(veterinarians, clinics, links, audit)

    with pytest.raises(ForbiddenError):
        link.execute(_link_command(uuid4(), uuid4(), permissions=frozenset()))
    with pytest.raises(NotFoundError):  # veterinário inexistente
        link.execute(_link_command(uuid4(), clinic_a.id))
    with pytest.raises(NotFoundError):  # clínica inexistente
        link.execute(_link_command(veterinarian.id, uuid4()))
    assert links.count_by_veterinarian(veterinarian.id) == 0

    link.execute(_link_command(veterinarian.id, clinic_a.id, primary=True))
    assert links.count_by_veterinarian(veterinarian.id) == 1
    assert audit.entries[-1].action == "veterinarian_clinics.linked"

    # Repetir o mesmo vínculo não duplica nem audita de novo.
    link.execute(_link_command(veterinarian.id, clinic_a.id, primary=True))
    assert links.count_by_veterinarian(veterinarian.id) == 1
    assert [e.action for e in audit.entries] == ["veterinarian_clinics.linked"]

    # Vincular outra clínica como não principal e depois promovê-la: só uma é principal.
    link.execute(_link_command(veterinarian.id, clinic_b.id))
    link.execute(_link_command(veterinarian.id, clinic_b.id, primary=True))
    remaining = links.list_by_veterinarian(veterinarian.id)
    assert len(remaining) == 2
    assert [item.clinic_id for item in remaining if item.primary_clinic] == [clinic_b.id]
    assert audit.entries[-1].action == "veterinarian_clinics.primary_changed"

    # Vincular direto como principal rebaixa a principal anterior.
    clinic_c = _clinic(name="Terceira")
    clinics.add(clinic_c)
    link.execute(_link_command(veterinarian.id, clinic_c.id, primary=True))
    primaries = [
        i.clinic_id for i in links.list_by_veterinarian(veterinarian.id) if i.primary_clinic
    ]
    assert primaries == [clinic_c.id]


def test_unlink_veterinarian_from_clinic_is_audited_idempotent_and_keeps_last_link() -> None:
    veterinarians, clinics, links, audit = _setup()
    autonomous = _veterinarian(is_autonomous=True)
    dependent = _veterinarian(is_autonomous=False)
    clinic = _clinic()
    veterinarians.add(autonomous)
    veterinarians.add(dependent)
    clinics.add(clinic)
    link = _link_use_case(veterinarians, clinics, links, audit)
    unlink = UnlinkVeterinarianFromClinicUseCase(
        veterinarians=veterinarians, links=links, audit=audit
    )
    actor = _actor(permissions=_MANAGER)
    link.execute(_link_command(autonomous.id, clinic.id))
    link.execute(_link_command(dependent.id, clinic.id))
    audit.entries.clear()

    # Desvincular quem não está vinculado não faz nada e não audita.
    unlink.execute(
        UnlinkVeterinarianFromClinicCommand(
            actor=actor, veterinarian_id=autonomous.id, clinic_id=uuid4()
        )
    )
    assert audit.entries == []

    unlink.execute(
        UnlinkVeterinarianFromClinicCommand(
            actor=actor, veterinarian_id=autonomous.id, clinic_id=clinic.id
        )
    )
    assert links.count_by_veterinarian(autonomous.id) == 0
    assert audit.entries[-1].action == "veterinarian_clinics.unlinked"

    # Não autônomo não pode perder a última clínica.
    with pytest.raises(LastClinicLinkRequiredError):
        unlink.execute(
            UnlinkVeterinarianFromClinicCommand(
                actor=actor, veterinarian_id=dependent.id, clinic_id=clinic.id
            )
        )
    assert links.count_by_veterinarian(dependent.id) == 1


def test_link_listings_resolve_names_and_respect_the_actor_clinic_scope() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian()
    own_clinic = _clinic(name="Propria")
    other_clinic = _clinic(name="Outra")
    veterinarians.add(veterinarian)
    clinics.add(own_clinic)
    clinics.add(other_clinic)
    link = _link_use_case(veterinarians, clinics, links, audit)
    link.execute(_link_command(veterinarian.id, own_clinic.id, primary=True))
    link.execute(_link_command(veterinarian.id, other_clinic.id))

    lab_actor = _actor(permissions=frozenset({"veterinarians.read", "clinics.read"}))
    by_veterinarian = ListClinicsForVeterinarianUseCase(links=links, clinics=clinics).execute(
        ListClinicsForVeterinarianQuery(actor=lab_actor, veterinarian_id=veterinarian.id)
    )
    assert {(c.clinic_name, c.primary_clinic) for c in by_veterinarian} == {
        ("Propria", True),
        ("Outra", False),
    }
    by_clinic = ListVeterinariansForClinicUseCase(links=links, veterinarians=veterinarians).execute(
        ListVeterinariansForClinicQuery(actor=lab_actor, clinic_id=own_clinic.id)
    )
    assert [v.veterinarian_name for v in by_clinic] == ["Dra. Fabianna Garcia"]

    clinic_actor = _clinic_actor(
        clinic_ids=frozenset({own_clinic.id}),
        permissions=frozenset({"veterinarians.read", "clinics.read"}),
    )
    scoped = ListClinicsForVeterinarianUseCase(links=links, clinics=clinics).execute(
        ListClinicsForVeterinarianQuery(actor=clinic_actor, veterinarian_id=veterinarian.id)
    )
    assert [c.clinic_id for c in scoped] == [own_clinic.id]
    with pytest.raises(NotFoundError):
        ListVeterinariansForClinicUseCase(links=links, veterinarians=veterinarians).execute(
            ListVeterinariansForClinicQuery(actor=clinic_actor, clinic_id=other_clinic.id)
        )
