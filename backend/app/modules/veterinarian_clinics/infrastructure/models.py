"""SQLAlchemy mapping for the veterinarian-clinic link module — separate
from domain entities (rule: .claude/rules/database.md, "não é Active
Record")."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class VeterinarianClinicModel(Base):
    __tablename__ = "veterinarian_clinics"
    __table_args__ = (
        UniqueConstraint(
            "veterinarian_id", "clinic_id", name="uq_veterinarian_clinics_veterinarian_clinic"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    veterinarian_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("veterinarians.id", ondelete="CASCADE"), nullable=False
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )
    primary_clinic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
