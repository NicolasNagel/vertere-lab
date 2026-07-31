"""Read one dotted field from a Claude hook JSON payload on stdin."""

from __future__ import annotations

import json
import sys
from typing import Any


def main() -> int:
    try:
        value: Any = json.load(sys.stdin)
        for key in sys.argv[1].split("."):
            value = value[key]
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return 0

    if isinstance(value, bool):
        print(str(value).lower())
    elif value is not None:
        print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
