from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.imports.application.list_import_exceptions import (
    ListImportExceptionsQuery,
    ListImportExceptionsUseCase,
)
from app.modules.imports.domain.entities import ImportException
from app.shared.domain.errors import ForbiddenError
from tests.imports.fakes import FakeImportExceptionRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_list_without_permission_is_forbidden() -> None:
    use_case = ListImportExceptionsUseCase(exceptions=FakeImportExceptionRepository())

    with pytest.raises(ForbiddenError):
        use_case.execute(ListImportExceptionsQuery(actor_permissions=frozenset(), batch_id=uuid4()))


def test_list_returns_only_exceptions_for_the_given_batch() -> None:
    batch_id = uuid4()
    other_batch_id = uuid4()
    repository = FakeImportExceptionRepository()
    repository.add_many(
        [
            ImportException(
                id=uuid4(),
                batch_id=batch_id,
                phase="clinics",
                source_row_number=3,
                message="teste",
                created_at=_NOW,
            ),
            ImportException(
                id=uuid4(),
                batch_id=other_batch_id,
                phase="clinics",
                source_row_number=4,
                message="outro lote",
                created_at=_NOW,
            ),
        ]
    )
    use_case = ListImportExceptionsUseCase(exceptions=repository)

    result = use_case.execute(
        ListImportExceptionsQuery(
            actor_permissions=frozenset({"imports.execute"}), batch_id=batch_id
        )
    )

    assert len(result) == 1
    assert result[0].batch_id == batch_id
