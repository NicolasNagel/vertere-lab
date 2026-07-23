"""One-time bootstrap: create the first SUPER_ADMIN user for an environment.

Run manually, never automatically from CI/deploy (rule:
.claude/rules/observability-performance-devops.md — migrations/bootstrap are
a controlled, single step, not a cold-start side effect).

Usage (from `backend/`):

    uv run python -m app.scripts.bootstrap_admin \\
        --email admin@vertere.local --full-name "Admin" --password "..."

Or via environment variables `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_FULL_NAME` /
`BOOTSTRAP_ADMIN_PASSWORD` instead of flags.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.identity.domain.value_objects import Email
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_SUPER_ADMIN
from app.shared.infrastructure.database import build_engine, build_session_factory


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=os.environ.get("BOOTSTRAP_ADMIN_EMAIL"))
    parser.add_argument("--full-name", default=os.environ.get("BOOTSTRAP_ADMIN_FULL_NAME", "Admin"))
    parser.add_argument("--password", default=os.environ.get("BOOTSTRAP_ADMIN_PASSWORD"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if not args.email or not args.password:
        print(
            "--email e --password (ou BOOTSTRAP_ADMIN_EMAIL/BOOTSTRAP_ADMIN_PASSWORD) são obrigatórios."
        )
        return 1

    email = Email(args.email)
    settings = get_settings()
    engine = build_engine(settings.database_url.get_secret_value())
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        existing = session.query(UserModel).filter(UserModel.email == str(email)).one_or_none()
        if existing is not None:
            print(f"Usuário {email} já existe — nada a fazer.")
            return 0

        now = datetime.now(UTC)
        user = UserModel(
            id=uuid4(),
            email=str(email),
            full_name=args.full_name,
            password_hash=hash_password(args.password),
            is_active=True,
            role_id=ROLE_SUPER_ADMIN,
            created_by=None,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()
        session.add(LabMembershipModel(id=uuid4(), user_id=user.id, is_active=True, granted_at=now))
        session.commit()
        print(f"Usuário SUPER_ADMIN criado: {email}")

    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
