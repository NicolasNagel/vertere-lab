"""List persisted exceptions for a batch — read-only, but still checks
permission at the use-case level (rule: .claude/rules/02-backend.md,
"autorização... em todo caso de uso, não só no router")."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.imports.domain.entities import ImportException
from app.modules.imports.domain.repositories import ImportExceptionRepository
from app.shared.domain.errors import ForbiddenError

_REQUIRED_PERMISSION = "imports.execute"


@dataclass(frozen=True, kw_only=True)
class ListImportExceptionsQuery:
    actor_permissions: frozenset[str]
    batch_id: UUID


class ListImportExceptionsUseCase:
    def __init__(self, *, exceptions: ImportExceptionRepository) -> None:
        self._exceptions = exceptions

    def execute(self, query: ListImportExceptionsQuery) -> list[ImportException]:
        if _REQUIRED_PERMISSION not in query.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        return self._exceptions.list_by_batch(query.batch_id)
