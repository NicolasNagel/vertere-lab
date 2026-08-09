"""Shared authorization context passed to application use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

RoleScope = Literal["GLOBAL", "LAB", "CLINIC"]


@dataclass(frozen=True, kw_only=True)
class ActorContext:
    user_id: UUID
    email: str
    full_name: str
    role_id: UUID
    role_name: str
    role_scope: RoleScope = "LAB"
    permissions: frozenset[str]
    clinic_ids: frozenset[UUID] = frozenset()
    row_version: int = 1

    @property
    def id(self) -> UUID:
        """Compatibility name while existing use cases migrate to `user_id`."""

        return self.user_id

    def can_access_clinic(self, clinic_id: UUID | None) -> bool:
        """Return whether this actor may address a clinic-owned resource."""

        return self.role_scope != "CLINIC" or (
            clinic_id is not None and clinic_id in self.clinic_ids
        )

    @property
    def clinic_filter(self) -> frozenset[UUID] | None:
        return self.clinic_ids if self.role_scope == "CLINIC" else None
