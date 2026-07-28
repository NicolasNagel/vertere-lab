"""Repository protocol for the billing module.

Read-only for this slice — the preview derives everything from
`attendances`/`attendance_exams`, never persists (rule:
.claude/rules/monthly-closure.md).
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.billing.domain.entities import ClosureCandidateItem, CompetencePeriod


class ClosurePreviewRepository(Protocol):
    def list_candidates(
        self, *, clinic_id: UUID, period: CompetencePeriod
    ) -> list[ClosureCandidateItem]: ...
