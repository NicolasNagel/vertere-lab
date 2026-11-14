"""Helpers de SQL compartilhados pela camada de infraestrutura."""

from __future__ import annotations

LIKE_ESCAPE = "\\"


def contains_pattern(value: str) -> str:
    """Monta o padrão "contém" para LIKE tratando %, _ e a barra invertida como texto.

    Sem isso, buscar "%" ou "_" casa com tudo e uma busca como "%%%%" vira varredura
    cara. Use junto com `escape=LIKE_ESCAPE` no `like`/`ilike`.
    """

    escaped = value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    escaped = escaped.replace("%", f"{LIKE_ESCAPE}%").replace("_", f"{LIKE_ESCAPE}_")
    return f"%{escaped}%"
