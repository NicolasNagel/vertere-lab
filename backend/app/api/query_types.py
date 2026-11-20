"""Query-parameter types shared by every list endpoint.

PostgreSQL text cannot hold a NUL byte, so a `%00` in a search term used to reach the database and
come back as a 500. These types reject it at the boundary with a field-level 422, and bound the size
of what is searched.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Query
from pydantic import AfterValidator

# 254 is the longest e-mail the login accepts, so a user can still be searched by it.
MAX_SEARCH_LENGTH = 254


def reject_nul[T: (str, None)](value: T) -> T:
    if value is not None and "\x00" in value:
        raise ValueError("O texto não pode conter o caractere NUL.")
    return value


SearchQuery = Annotated[str | None, Query(max_length=MAX_SEARCH_LENGTH), AfterValidator(reject_nul)]
ProtocolQuery = Annotated[
    str | None, Query(min_length=1, max_length=32), AfterValidator(reject_nul)
]
OwnerNameQuery = Annotated[
    str | None, Query(min_length=1, max_length=200), AfterValidator(reject_nul)
]
# Required: a change reason sent in the query string (the DELETE has no body).
ReasonQuery = Annotated[str, Query(min_length=1, max_length=500), AfterValidator(reject_nul)]
