from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.modules.patients.application.list_species import ListSpeciesQuery, ListSpeciesUseCase
from app.modules.patients.domain.entities import Species
from app.shared.domain.errors import ForbiddenError
from tests.patients.fakes import FakeSpeciesRepository

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


def test_list_species_requires_permission() -> None:
    use_case = ListSpeciesUseCase(species=FakeSpeciesRepository())

    with pytest.raises(ForbiddenError):
        use_case.execute(ListSpeciesQuery(actor=_actor(permissions=frozenset())))


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
