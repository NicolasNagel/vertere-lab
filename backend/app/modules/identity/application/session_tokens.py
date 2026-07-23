from __future__ import annotations

from typing import Protocol


class SessionTokenGenerator(Protocol):
    def generate(self) -> str: ...

    def hash(self, token: str) -> str: ...
