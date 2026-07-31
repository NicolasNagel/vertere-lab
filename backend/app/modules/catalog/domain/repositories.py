"""Repository protocols for the catalog module.

Interfaces live in `domain` (per .claude/rules/02-backend.md); implementations
live in `infrastructure`. Repositories never commit — the unit of work
does.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.catalog.domain.entities import Exam, ExamCategory, ExamCategoryStatus, ExamStatus


class ExamCategoryRepository(Protocol):
    def get_by_id(self, category_id: UUID) -> ExamCategory | None: ...

    def get_by_name(self, name: str) -> ExamCategory | None: ...

    def add(self, category: ExamCategory) -> None: ...

    def save(self, category: ExamCategory) -> None: ...

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ExamCategoryStatus | None,
        search: str | None,
    ) -> tuple[list[ExamCategory], int]: ...

    def list_all_active(self) -> list[ExamCategory]: ...


class ExamRepository(Protocol):
    def get_by_id(self, exam_id: UUID) -> Exam | None: ...

    def get_by_code(self, code: str) -> Exam | None: ...

    def list_all_names(self) -> dict[str, UUID]:
        """Case-insensitive name -> id, for bulk name resolution (import).
        Not paginated on purpose: callers need the *whole* set to resolve a
        batch of rows without one query per row."""
        ...

    def add(self, exam: Exam) -> None: ...

    def save(self, exam: Exam) -> None: ...

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ExamStatus | None,
        category_id: UUID | None,
        species_id: UUID | None,
        search: str | None,
    ) -> tuple[list[Exam], int]: ...
