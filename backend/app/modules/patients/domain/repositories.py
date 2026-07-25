"""Repository protocol for the patients module (species slice).

Interface lives in `domain` (per .claude/rules/backend.md); implementation
lives in `infrastructure`.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.patients.domain.entities import Species


class SpeciesRepository(Protocol):
    def list_all(self) -> list[Species]: ...
