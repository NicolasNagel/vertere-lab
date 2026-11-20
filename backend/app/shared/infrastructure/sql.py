"""Helpers de SQL compartilhados pela camada de infraestrutura."""

from __future__ import annotations

from sqlalchemy import ColumnElement, func
from sqlalchemy.sql.elements import SQLCoreOperations

LIKE_ESCAPE = "\\"


def folded(column: SQLCoreOperations[str] | SQLCoreOperations[str | None]) -> ColumnElement[str]:
    """`lower(unaccent(column))`, so "joao" finds "João" (needs the `unaccent` extension, migration 0044)."""
    return func.lower(func.unaccent(column))


def contains_pattern(value: str) -> str:
    """Monta o padrão "contém" para LIKE tratando %, _ e a barra invertida como texto.

    Sem isso, buscar "%" ou "_" casa com tudo e uma busca como "%%%%" vira varredura
    cara. Use junto com `escape=LIKE_ESCAPE` no `like`/`ilike`.
    """

    escaped = value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    escaped = escaped.replace("%", f"{LIKE_ESCAPE}%").replace("_", f"{LIKE_ESCAPE}_")
    return f"%{escaped}%"


def folded_pattern(term: str) -> ColumnElement[str]:
    """The LIKE pattern for `term`, folded by the SAME `lower(unaccent())` as the column.

    Folding in the database (not in Python) keeps both sides symmetric for every character
    `unaccent` knows, including those with no Unicode decomposition (ø, ł, ß).
    """
    return func.lower(func.unaccent(contains_pattern(term)))
