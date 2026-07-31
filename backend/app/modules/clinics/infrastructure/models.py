"""SQLAlchemy mapping for the clinics module — separate from domain
entities (rule: .claude/rules/03-database.md, "não é Active Record")."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class ClinicModel(Base):
    __tablename__ = "clinics"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE','DELINQUENT','SPECIAL')", name="ck_clinics_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    tax_id: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(nullable=True)
    email: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="ACTIVE")
    address_zip_code: Mapped[str | None] = mapped_column(nullable=True)
    address_street: Mapped[str | None] = mapped_column(nullable=True)
    address_number: Mapped[str | None] = mapped_column(nullable=True)
    address_neighborhood: Mapped[str | None] = mapped_column(nullable=True)
    address_city: Mapped[str | None] = mapped_column(nullable=True)
    address_state: Mapped[str | None] = mapped_column(nullable=True)
    address_complement: Mapped[str | None] = mapped_column(nullable=True)
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
