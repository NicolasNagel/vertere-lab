"""Application-layer DTOs shared across modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class PageDTO[T]:
    items: list[T]
    total: int
    page: int
    page_size: int
