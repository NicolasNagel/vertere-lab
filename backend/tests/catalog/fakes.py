"""In-memory fakes for the catalog module repository protocols — used by
unit tests for use cases (rule: mock only at an external boundary; a fake
repository backing a pure use-case test is not the repository-under-test,
so this is fine per .claude/rules/testing.md)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.audit.domain.entities import AuditEntry
from app.modules.catalog.domain.entities import Exam, ExamCategory, ExamCategoryStatus, ExamStatus
from app.modules.patients.domain.entities import Species


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeAuditLogWriter:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class FakeExamCategoryRepository:
    def __init__(self) -> None:
        self._categories: dict[UUID, ExamCategory] = {}

    def add(self, category: ExamCategory) -> None:
        self._categories[category.id] = category

    def save(self, category: ExamCategory) -> None:
        category.row_version += 1
        self._categories[category.id] = category

    def get_by_id(self, category_id: UUID) -> ExamCategory | None:
        return self._categories.get(category_id)

    def get_by_name(self, name: str) -> ExamCategory | None:
        for category in self._categories.values():
            if category.name.lower() == name.lower():
                return category
        return None

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ExamCategoryStatus | None,
        search: str | None,
    ) -> tuple[list[ExamCategory], int]:
        categories = list(self._categories.values())
        if status is not None:
            categories = [c for c in categories if c.status == status]
        if search:
            needle = search.lower()
            categories = [c for c in categories if needle in c.name.lower()]
        return categories, len(categories)

    def list_all_active(self) -> list[ExamCategory]:
        return [c for c in self._categories.values() if c.status == ExamCategoryStatus.ACTIVE]


class FakeExamRepository:
    def __init__(self) -> None:
        self._exams: dict[UUID, Exam] = {}

    def add(self, exam: Exam) -> None:
        self._exams[exam.id] = exam

    def save(self, exam: Exam) -> None:
        exam.row_version += 1
        self._exams[exam.id] = exam

    def get_by_id(self, exam_id: UUID) -> Exam | None:
        return self._exams.get(exam_id)

    def get_by_code(self, code: str) -> Exam | None:
        for exam in self._exams.values():
            if str(exam.code) == code:
                return exam
        return None

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ExamStatus | None,
        category_id: UUID | None,
        species_id: UUID | None,
        search: str | None,
    ) -> tuple[list[Exam], int]:
        exams = list(self._exams.values())
        if status is not None:
            exams = [e for e in exams if e.status == status]
        if category_id is not None:
            exams = [e for e in exams if e.category_id == category_id]
        if species_id is not None:
            exams = [e for e in exams if species_id in e.species_ids]
        if search:
            needle = search.lower()
            exams = [e for e in exams if needle in e.name.lower() or needle in str(e.code).lower()]
        return exams, len(exams)


class FakeSpeciesRepository:
    def __init__(self, species: list[Species] | None = None) -> None:
        self._species = list(species or [])

    def list_all(self) -> list[Species]:
        return sorted(self._species, key=lambda item: item.name)
