"""Clock contract — use cases depend on this, never on `datetime.now()`
directly, so tests can control time (rule: .claude/rules/08-testing.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
