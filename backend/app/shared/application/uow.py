"""Unit of work contract.

Use cases own the transaction boundary through this protocol; repositories
never commit on their own. The SQLAlchemy implementation lives in
``app.shared.infrastructure.uow``.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self


class UnitOfWork(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
