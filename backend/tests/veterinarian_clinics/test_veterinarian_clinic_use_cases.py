from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

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
        id=uuid4(),
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


def test_link_veterinarian_to_clinic_succeeds_and_audits() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian()
    clinic = _clinic()
    veterinarians.add(veterinarian)
    clinics.add(clinic)

    use_case = LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    )
    use_case.execute(
        LinkVeterinarianToClinicCommand(
            actor=_actor(permissions=frozenset({"veterinarians.manage"})),
            veterinarian_id=veterinarian.id,
            clinic_id=clinic.id,
            primary_clinic=True,
        )
    )

    assert links.count_by_veterinarian(veterinarian.id) == 1
    assert audit.entries[-1].action == "veterinarian_clinics.linked"


def test_link_veterinarian_to_clinic_is_idempotent() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian()
    clinic = _clinic()
    veterinarians.add(veterinarian)
    clinics.add(clinic)

    use_case = LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    )
    command = LinkVeterinarianToClinicCommand(
        actor=_actor(permissions=frozenset({"veterinarians.manage"})),
        veterinarian_id=veterinarian.id,
        clinic_id=clinic.id,
        primary_clinic=False,
    )
    use_case.execute(command)
    use_case.execute(command)

    assert links.count_by_veterinarian(veterinarian.id) == 1
    assert len([e for e in audit.entries if e.action == "veterinarian_clinics.linked"]) == 1


def test_link_veterinarian_to_clinic_promotes_existing_link_to_primary() -> None:
    """Re-linking an already-linked clinic with `primary_clinic=True` must
    still promote it, not silently no-op — see docstring of
    LinkVeterinarianToClinicUseCase."""
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian()
    clinic_a = _clinic(name="Schweitzer")
    clinic_b = _clinic(name="Bicho Urbano")
    veterinarians.add(veterinarian)
    clinics.add(clinic_a)
    clinics.add(clinic_b)

    use_case = LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    )
    actor = _actor(permissions=frozenset({"veterinarians.manage"}))
    use_case.execute(
        LinkVeterinarianToClinicCommand(
            actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic_a.id, primary_clinic=True
        )
    )
    use_case.execute(
        LinkVeterinarianToClinicCommand(
            actor=actor,
            veterinarian_id=veterinarian.id,
            clinic_id=clinic_b.id,
            primary_clinic=False,
        )
    )

    # clinic_b is already linked (not primary) — asking to link it again as
    # primary must promote it, not no-op.
    use_case.execute(
        LinkVeterinarianToClinicCommand(
            actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic_b.id, primary_clinic=True
        )
    )

    remaining = links.list_by_veterinarian(veterinarian.id)
    assert len(remaining) == 2
    primaries = [link for link in remaining if link.primary_clinic]
    assert len(primaries) == 1
    assert primaries[0].clinic_id == clinic_b.id
    assert audit.entries[-1].action == "veterinarian_clinics.primary_changed"


def test_link_veterinarian_to_clinic_clears_previous_primary() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian()
    clinic_a = _clinic(name="Schweitzer")
    clinic_b = _clinic(name="Bicho Urbano")
    veterinarians.add(veterinarian)
    clinics.add(clinic_a)
    clinics.add(clinic_b)

    use_case = LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    )
    actor = _actor(permissions=frozenset({"veterinarians.manage"}))
    use_case.execute(
        LinkVeterinarianToClinicCommand(
            actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic_a.id, primary_clinic=True
        )
    )
    use_case.execute(
        LinkVeterinarianToClinicCommand(
            actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic_b.id, primary_clinic=True
        )
    )

    remaining = links.list_by_veterinarian(veterinarian.id)
    primaries = [link for link in remaining if link.primary_clinic]
    assert len(primaries) == 1
    assert primaries[0].clinic_id == clinic_b.id


def test_link_veterinarian_to_clinic_requires_permission() -> None:
    veterinarians, clinics, links, audit = _setup()
    use_case = LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    )

    with pytest.raises(ForbiddenError):
        use_case.execute(
            LinkVeterinarianToClinicCommand(
                actor=_actor(permissions=frozenset()),
                veterinarian_id=uuid4(),
                clinic_id=uuid4(),
                primary_clinic=False,
            )
        )


def test_link_veterinarian_to_clinic_veterinarian_not_found() -> None:
    veterinarians, clinics, links, audit = _setup()
    clinic = _clinic()
    clinics.add(clinic)
    use_case = LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            LinkVeterinarianToClinicCommand(
                actor=_actor(permissions=frozenset({"veterinarians.manage"})),
                veterinarian_id=uuid4(),
                clinic_id=clinic.id,
                primary_clinic=False,
            )
        )


def test_link_veterinarian_to_clinic_clinic_not_found() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian()
    veterinarians.add(veterinarian)
    use_case = LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            LinkVeterinarianToClinicCommand(
                actor=_actor(permissions=frozenset({"veterinarians.manage"})),
                veterinarian_id=veterinarian.id,
                clinic_id=uuid4(),
                primary_clinic=False,
            )
        )


def test_unlink_veterinarian_from_clinic_succeeds_and_audits() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian(is_autonomous=True)
    clinic = _clinic()
    veterinarians.add(veterinarian)
    clinics.add(clinic)
    link_use_case = LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    )
    actor = _actor(permissions=frozenset({"veterinarians.manage"}))
    link_use_case.execute(
        LinkVeterinarianToClinicCommand(
            actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic.id, primary_clinic=False
        )
    )

    unlink_use_case = UnlinkVeterinarianFromClinicUseCase(
        veterinarians=veterinarians, links=links, audit=audit
    )
    unlink_use_case.execute(
        UnlinkVeterinarianFromClinicCommand(
            actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic.id
        )
    )

    assert links.count_by_veterinarian(veterinarian.id) == 0
    assert audit.entries[-1].action == "veterinarian_clinics.unlinked"


def test_unlink_veterinarian_from_clinic_is_idempotent_when_not_linked() -> None:
    veterinarians, _clinics, links, audit = _setup()
    veterinarian = _veterinarian(is_autonomous=True)
    veterinarians.add(veterinarian)

    use_case = UnlinkVeterinarianFromClinicUseCase(
        veterinarians=veterinarians, links=links, audit=audit
    )
    use_case.execute(
        UnlinkVeterinarianFromClinicCommand(
            actor=_actor(permissions=frozenset({"veterinarians.manage"})),
            veterinarian_id=veterinarian.id,
            clinic_id=uuid4(),
        )
    )

    assert audit.entries == []


def test_unlink_veterinarian_from_clinic_blocks_last_link_for_non_autonomous() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian(is_autonomous=False)
    clinic = _clinic()
    veterinarians.add(veterinarian)
    clinics.add(clinic)
    actor = _actor(permissions=frozenset({"veterinarians.manage"}))
    LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    ).execute(
        LinkVeterinarianToClinicCommand(
            actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic.id, primary_clinic=False
        )
    )

    unlink_use_case = UnlinkVeterinarianFromClinicUseCase(
        veterinarians=veterinarians, links=links, audit=audit
    )
    with pytest.raises(LastClinicLinkRequiredError):
        unlink_use_case.execute(
            UnlinkVeterinarianFromClinicCommand(
                actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic.id
            )
        )

    assert links.count_by_veterinarian(veterinarian.id) == 1


def test_list_clinics_for_veterinarian_resolves_names() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian()
    clinic = _clinic(name="Schweitzer")
    veterinarians.add(veterinarian)
    clinics.add(clinic)
    actor = _actor(permissions=frozenset({"veterinarians.manage", "veterinarians.read"}))
    LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    ).execute(
        LinkVeterinarianToClinicCommand(
            actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic.id, primary_clinic=True
        )
    )

    result = ListClinicsForVeterinarianUseCase(links=links, clinics=clinics).execute(
        ListClinicsForVeterinarianQuery(actor=actor, veterinarian_id=veterinarian.id)
    )

    assert len(result) == 1
    assert result[0].clinic_name == "Schweitzer"
    assert result[0].primary_clinic is True


def test_list_veterinarians_for_clinic_resolves_names() -> None:
    veterinarians, clinics, links, audit = _setup()
    veterinarian = _veterinarian()
    clinic = _clinic(name="Schweitzer")
    veterinarians.add(veterinarian)
    clinics.add(clinic)
    actor = _actor(permissions=frozenset({"veterinarians.manage", "clinics.read"}))
    LinkVeterinarianToClinicUseCase(
        veterinarians=veterinarians,
        clinics=clinics,
        links=links,
        audit=audit,
        clock=FakeClock(_NOW),
    ).execute(
        LinkVeterinarianToClinicCommand(
            actor=actor, veterinarian_id=veterinarian.id, clinic_id=clinic.id, primary_clinic=False
        )
    )

    result = ListVeterinariansForClinicUseCase(links=links, veterinarians=veterinarians).execute(
        ListVeterinariansForClinicQuery(actor=actor, clinic_id=clinic.id)
    )

    assert len(result) == 1
    assert result[0].veterinarian_name == "Dra. Fabianna Garcia"
