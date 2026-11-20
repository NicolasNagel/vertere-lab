"""Which users a clinic-scope actor may see or change.

A clinic-scope actor addresses only users that belong to its own clinics and to NO other clinic:
a user shared with another clinic, a laboratory user or one without clinics is outside its scope.
Outside scope answers 404 (never 403), like every other clinic-owned resource, so it does not
confirm that the user exists.
"""

from __future__ import annotations

from uuid import UUID

from app.modules.identity.domain.entities import Role, RoleScope
from app.modules.identity.domain.repositories import ClinicMembershipRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import ForbiddenError, NotFoundError


def ensure_user_in_actor_scope(
    actor: ActorContext, user_id: UUID, clinic_memberships: ClinicMembershipRepository
) -> None:
    allowed = actor.clinic_filter
    if allowed is None:
        return
    user_clinics = clinic_memberships.list_active_clinic_ids_for_user(user_id)
    if not user_clinics or not user_clinics <= allowed:
        raise NotFoundError("Usuário não encontrado.")


def ensure_role_grantable(actor: ActorContext, role: Role) -> None:
    """A clinic actor may only hand out clinic roles that do not exceed its own permissions.

    Without the subset rule it could give itself (or a colleague) a stronger role, e.g. one with
    closures or pricing, and escalate inside its own clinic.
    """
    if actor.clinic_filter is None:
        return
    if role.scope is not RoleScope.CLINIC or not role.permission_codes <= actor.permissions:
        raise ForbiddenError("Não é permitido conceder um papel com mais permissões que as suas.")
