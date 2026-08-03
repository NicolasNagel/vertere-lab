"""SQLAlchemy mapping for the billing module's persistent entities —
separate from the domain entities (rule: .claude/rules/03-database.md, "não é
Active Record").

`ClosurePreview*` (Incremento 4.1) never persists, so it has no model here —
only `MonthlyClosure`/`MonthlyClosureItem` (Incremento 4.2) do.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.infrastructure.database import Base


class MonthlyClosureModel(Base):
    __tablename__ = "monthly_closures"
    __table_args__ = (
        CheckConstraint("status IN ('CLOSED','REOPENED')", name="ck_monthly_closures_status"),
        CheckConstraint("subtotal >= 0", name="ck_monthly_closures_subtotal_non_negative"),
        CheckConstraint(
            "discount_total >= 0", name="ck_monthly_closures_discount_total_non_negative"
        ),
        CheckConstraint(
            "surcharge_total >= 0", name="ck_monthly_closures_surcharge_total_non_negative"
        ),
        CheckConstraint(
            "on_call_fee_total >= 0", name="ck_monthly_closures_on_call_fee_total_non_negative"
        ),
        CheckConstraint("grand_total >= 0", name="ck_monthly_closures_grand_total_non_negative"),
        CheckConstraint("item_count >= 0", name="ck_monthly_closures_item_count_non_negative"),
        # Partial unique index: only one *active* (CLOSED) closure per
        # clinic+competence at a time — a future REOPENED row does not
        # collide with a subsequent re-close (`.claude/rules/13-monthly-closure.md`:
        # "unicidade ativa por clínica e competência").
        Index(
            "uq_monthly_closures_active_clinic_competence",
            "clinic_id",
            "competence_year",
            "competence_month",
            unique=True,
            postgresql_where=text("status = 'CLOSED'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="RESTRICT"), nullable=False
    )
    competence_year: Mapped[int] = mapped_column(nullable=False)
    competence_month: Mapped[int] = mapped_column(nullable=False)
    period_start: Mapped[date] = mapped_column(nullable=False)
    period_end: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="CLOSED")
    item_count: Mapped[int] = mapped_column(nullable=False, default=0)
    subtotal: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    surcharge_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    on_call_fee_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    grand_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    generated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    closed_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    reopened_at: Mapped[datetime | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    integrity_hash: Mapped[str | None] = mapped_column(nullable=True)

    items: Mapped[list[MonthlyClosureItemModel]] = relationship(
        back_populates="monthly_closure", cascade="all, delete-orphan"
    )
    adjustments: Mapped[list[FinancialAdjustmentModel]] = relationship(
        back_populates="monthly_closure"
    )


class MonthlyClosureItemModel(Base):
    __tablename__ = "monthly_closure_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_monthly_closure_items_quantity_positive"),
        CheckConstraint(
            "discount_amount >= 0", name="ck_monthly_closure_items_discount_non_negative"
        ),
        CheckConstraint(
            "surcharge_amount >= 0", name="ck_monthly_closure_items_surcharge_non_negative"
        ),
        CheckConstraint("total_amount >= 0", name="ck_monthly_closure_items_total_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    monthly_closure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("monthly_closures.id", ondelete="CASCADE"), nullable=False
    )
    attendance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendances.id", ondelete="RESTRICT"), nullable=False
    )
    attendance_exam_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_exams.id", ondelete="RESTRICT"), nullable=False
    )
    protocol_number: Mapped[str | None] = mapped_column(nullable=True)
    patient_name: Mapped[str] = mapped_column(nullable=False)
    exam_name: Mapped[str] = mapped_column(nullable=False)
    price_base: Mapped[Decimal] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    discount_amount: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    surcharge_amount: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(nullable=False)

    monthly_closure: Mapped[MonthlyClosureModel] = relationship(back_populates="items")


class FinancialAdjustmentModel(Base):
    __tablename__ = "financial_adjustments"
    __table_args__ = (
        CheckConstraint("kind IN ('CREDIT','DEBIT')", name="ck_financial_adjustments_kind"),
        CheckConstraint("amount > 0", name="ck_financial_adjustments_amount_positive"),
        Index(
            "ix_financial_adjustments_closure_created_at",
            "monthly_closure_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    monthly_closure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("monthly_closures.id", ondelete="RESTRICT"), nullable=False
    )
    monthly_closure_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("monthly_closure_items.id", ondelete="RESTRICT"), nullable=True
    )
    kind: Mapped[str] = mapped_column(nullable=False)
    amount: Mapped[Decimal] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    monthly_closure: Mapped[MonthlyClosureModel] = relationship(back_populates="adjustments")
