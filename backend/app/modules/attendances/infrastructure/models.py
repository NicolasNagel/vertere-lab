"""SQLAlchemy mapping for the attendances module — separate from domain
entities (rule: .claude/rules/database.md, "não é Active Record")."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.infrastructure.database import Base


class AttendanceModel(Base):
    __tablename__ = "attendances"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED','ON_HOLD')",
            name="ck_attendances_status",
        ),
        CheckConstraint("subtotal >= 0", name="ck_attendances_subtotal_non_negative"),
        CheckConstraint("discount_total >= 0", name="ck_attendances_discount_total_non_negative"),
        CheckConstraint("surcharge_total >= 0", name="ck_attendances_surcharge_total_non_negative"),
        CheckConstraint("grand_total >= 0", name="ck_attendances_grand_total_non_negative"),
        UniqueConstraint(
            "protocol_year", "protocol_sequence", name="uq_attendances_protocol_year_sequence"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="RESTRICT"), nullable=False
    )
    veterinarian_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("veterinarians.id", ondelete="RESTRICT"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    service_date: Mapped[date | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="DRAFT")
    billing_competence: Mapped[date | None] = mapped_column(nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    surcharge_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    protocol_year: Mapped[int | None] = mapped_column(nullable=True)
    protocol_sequence: Mapped[int | None] = mapped_column(nullable=True)
    protocol_number: Mapped[str | None] = mapped_column(nullable=True)
    # No FK yet — `monthly_closures` only exists from Incremento 4.2 on.
    monthly_closure_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
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

    items: Mapped[list[AttendanceExamModel]] = relationship(
        back_populates="attendance", cascade="all, delete-orphan"
    )


class AttendanceExamModel(Base):
    __tablename__ = "attendance_exams"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_attendance_exams_quantity_positive"),
        CheckConstraint("discount_amount >= 0", name="ck_attendance_exams_discount_non_negative"),
        CheckConstraint("surcharge_amount >= 0", name="ck_attendance_exams_surcharge_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_attendance_exams_total_non_negative"),
        CheckConstraint("status IN ('ACTIVE','CANCELLED')", name="ck_attendance_exams_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    attendance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendances.id", ondelete="CASCADE"), nullable=False
    )
    exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exams.id", ondelete="RESTRICT"), nullable=False
    )
    exam_code: Mapped[str] = mapped_column(nullable=False)
    exam_name: Mapped[str] = mapped_column(nullable=False)
    price_base: Mapped[Decimal] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    discount_amount: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    surcharge_amount: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(nullable=False)
    override_reason: Mapped[str | None] = mapped_column(nullable=True)
    override_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    attendance: Mapped[AttendanceModel] = relationship(back_populates="items")


class AttendanceSequenceModel(Base):
    """Transactional protocol counter, one row per year — `SELECT ... FOR
    UPDATE` in the repository, never `MAX + 1` (`.claude/rules/database.md`).
    """

    __tablename__ = "attendance_sequences"

    year: Mapped[int] = mapped_column(primary_key=True)
    last_sequence: Mapped[int] = mapped_column(nullable=False, default=0)
