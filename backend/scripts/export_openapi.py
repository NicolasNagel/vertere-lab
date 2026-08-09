"""Export the application OpenAPI contract without opening a database connection."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    target = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
    settings = Settings(database_url="postgresql+psycopg://openapi:openapi@localhost/openapi")
    target.write_text(
        json.dumps(create_app(settings).openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
