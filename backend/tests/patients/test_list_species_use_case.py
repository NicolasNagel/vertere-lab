from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.application.list_species import ListSpeciesQuery, ListSpeciesUseCase
from app.modules.patients.domain.entities import Species
from tests.patients.fakes import FakeSpeciesRepository

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


def test_list_species_has_no_permission_gate() -> None:
    repository = FakeSpeciesRepository([Species(id=uuid4(), name="Cão", created_at=_NOW)])
    use_case = ListSpeciesUseCase(species=repository)

    result = use_case.execute(ListSpeciesQuery(actor=_actor(permissions=frozenset())))

    assert [item.name for item in result] == ["Cão"]


def test_list_species_returns_catalog_sorted_by_name() -> None:
    repository = FakeSpeciesRepository(
        [
            Species(id=uuid4(), name="Gato", created_at=_NOW),
            Species(id=uuid4(), name="Cão", created_at=_NOW),
        ]
    )
    use_case = ListSpeciesUseCase(species=repository)

    result = use_case.execute(
        ListSpeciesQuery(actor=_actor(permissions=frozenset({"patients.read"})))
    )

    assert [item.name for item in result] == ["Cão", "Gato"]
