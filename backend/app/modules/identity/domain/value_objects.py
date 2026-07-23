"""Value objects for the identity domain — immutable, self-validating."""

from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PERMISSION_CODE_PATTERN = re.compile(r"^[a-z_]+\.[a-z_]+$")


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not _EMAIL_PATTERN.match(normalized):
            raise ValueError(f"E-mail inválido: {self.value!r}")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PermissionCode:
    value: str

    def __post_init__(self) -> None:
        if not _PERMISSION_CODE_PATTERN.match(self.value):
            raise ValueError(f"Código de permissão inválido: {self.value!r}")

    def __str__(self) -> str:
        return self.value
