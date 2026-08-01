"""SQLAlchemy mapping for the catalog module — separate from domain
entities (rule: .claude/rules/03-database.md, "não é Active Record")."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.database import Base


class ExamCategoryModel(Base):
    __tablename__ = "exam_categories"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_exam_categories_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="ACTIVE")
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


class ExamModel(Base):
    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_exams_status"),
        CheckConstraint("price_base > 0", name="ck_exams_price_base_positive"),
        CheckConstraint(
            "price_valid_to IS NULL OR price_valid_to >= price_valid_from",
            name="ck_exams_price_validity",
        ),
        CheckConstraint(
            "plantao_surcharge_fixed IS NULL OR plantao_surcharge_percent IS NULL",
            name="ck_exams_plantao_surcharge_exclusive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_categories.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(nullable=True)
    price_base: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    price_valid_from: Mapped[date] = mapped_column(nullable=False, default=date(1900, 1, 1))
    price_valid_to: Mapped[date | None] = mapped_column(nullable=True)
    plantao_surcharge_fixed: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    plantao_surcharge_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="ACTIVE")
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


class ExamSpeciesModel(Base):
    __tablename__ = "exam_species"
    __table_args__ = (
        UniqueConstraint("exam_id", "species_id", name="uq_exam_species_exam_species"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), nullable=False
    )
    species_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("species.id", ondelete="RESTRICT"), nullable=False
    )
