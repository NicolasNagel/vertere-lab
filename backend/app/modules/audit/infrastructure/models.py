"""SQLAlchemy mapping for `audit_log` — separate from the domain entity.

Append-only by convention: no code path in this module issues UPDATE/DELETE
against this table.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class AuditLogModel(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_audit_log_actor_user_id", "actor_user_id"),
        Index("ix_audit_log_occurred_at", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_scope: Mapped[str] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(nullable=False)
    entity_type: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[str | None] = mapped_column(nullable=True)
    before_state: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(nullable=True)
    ip_address: Mapped[str | None] = mapped_column(nullable=True)
    request_id: Mapped[str | None] = mapped_column(nullable=True)
