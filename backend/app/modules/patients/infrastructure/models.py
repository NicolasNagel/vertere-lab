"""SQLAlchemy mapping for the patients module (species slice) — separate
from domain entities (rule: .claude/rules/database.md, "não é Active
Record")."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class SpeciesModel(Base):
    __tablename__ = "species"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
