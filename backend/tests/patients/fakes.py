"""In-memory fake for the species repository protocol — used by unit tests
for use cases (rule: mock only at an external boundary; a fake repository
backing a pure use-case test is not the repository-under-test, so this is
fine per .claude/rules/testing.md)."""

from __future__ import annotations

from app.modules.patients.domain.entities import Species


class FakeSpeciesRepository:
    def __init__(self, species: list[Species] | None = None) -> None:
        self._species = list(species or [])

    def list_all(self) -> list[Species]:
        return sorted(self._species, key=lambda item: item.name)
