"""Address-lookup domain entities.

No FastAPI/httpx import here (rule: .claude/rules/00-global.md — domain
layer). This is a read-only lookup result, not a persisted aggregate, so it
has no id/audit fields.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CepAddress:
    zip_code: str
    street: str | None
    neighborhood: str | None
    city: str | None
    state: str | None
