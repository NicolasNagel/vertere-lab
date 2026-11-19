"""Helpers de SQL compartilhados pela camada de infraestrutura."""

from __future__ import annotations

import unicodedata

from sqlalchemy import ColumnElement, func
from sqlalchemy.sql.elements import SQLCoreOperations

LIKE_ESCAPE = "\\"


def fold(text: str) -> str:
    """Lowercase and strip accents: the Python twin of `folded(column)`, for the search term.

    NFD removes combining marks (ã, ç, é, ü: all of Portuguese). PostgreSQL `unaccent` also maps letters
    with no decomposition (ø, đ, ł, ß, æ), which this does not, so such terms need the exact form.
    """
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


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
