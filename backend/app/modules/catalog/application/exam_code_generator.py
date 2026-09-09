"""Generation policy for internal exam codes."""

from __future__ import annotations

import secrets
import string
from collections.abc import Callable

ExamCodeGenerator = Callable[[], str]

_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


def generate_exam_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))
