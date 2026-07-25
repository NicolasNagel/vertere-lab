"""SQLAlchemy mapping for the patients module (species slice) — separate
from domain entities (rule: .claude/rules/database.md, "não é Active
Record")."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class SpeciesModel(Base):
    __tablename__ = "species"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class PatientModel(Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint("sex IN ('MALE','FEMALE')", name="ck_patients_sex"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_patients_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    species_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("species.id", ondelete="RESTRICT"), nullable=False
    )
    sex: Mapped[str] = mapped_column(nullable=False)
    breed: Mapped[str | None] = mapped_column(nullable=True)
    age_description: Mapped[str | None] = mapped_column(nullable=True)
    owner_name: Mapped[str] = mapped_column(nullable=False)
    owner_phone: Mapped[str | None] = mapped_column(nullable=True)
    owner_document: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="ACTIVE")
    notes: Mapped[str | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
    row_version: Mapped[int] = mapped_column(nullable=False, default=1)
