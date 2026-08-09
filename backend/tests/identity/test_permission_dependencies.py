from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.identity.api.dependencies import require_permission
from app.shared.application.authorization import ActorContext, RoleScope
from app.shared.domain.errors import ForbiddenError


def _actor(*, role_scope: RoleScope) -> ActorContext:
    return ActorContext(
        user_id=uuid4(),
        email="actor@vertere.local",
        full_name="Actor",
        role_id=uuid4(),
        role_name="CUSTOM",
        role_scope=role_scope,
        permissions=frozenset({"imports.execute"}),
    )


def test_allowed_scopes_rejects_clinic_even_when_permission_was_misconfigured() -> None:
    dependency = require_permission("imports.execute", allowed_scopes=frozenset({"GLOBAL", "LAB"}))

    with pytest.raises(ForbiddenError, match="exclusivo do laboratório"):
        dependency(current_user=_actor(role_scope="CLINIC"))


def test_allowed_scopes_accepts_lab_actor_with_permission() -> None:
    dependency = require_permission("imports.execute", allowed_scopes=frozenset({"GLOBAL", "LAB"}))

    assert dependency(current_user=_actor(role_scope="LAB")).role_scope == "LAB"
