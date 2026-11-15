"""SQLAlchemy mapping for the attendances module — separate from domain
entities (rule: .claude/rules/03-database.md, "não é Active Record")."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    SmallInteger,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.infrastructure.database import Base


class AttendanceModel(Base):
    """`version_id_col=row_version` makes every `UPDATE` carry `WHERE
    row_version = <value loaded by this session>` and auto-increments it —
    a second transaction racing on the same row (e.g. two concurrent
    `/cancel` calls) finds 0 rows affected and SQLAlchemy raises
    `StaleDataError`, mapped to `409 CONFLICT` in `api/error_handlers.py`.
    Without this, two concurrent reads-before-either-commits both pass the
    domain's in-memory state check and both `UPDATE` "successfully" — the
    lost-update race a plain `SELECT` + `UPDATE` can never rule out on its
    own (`.claude/rules/12-attendance.md`: "toda edição usa row version").
    """

    __tablename__ = "attendances"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','IN_PROGRESS','COMPLETED','CANCELLED','ON_HOLD')",
            name="ck_attendances_status",
        ),
        CheckConstraint("subtotal >= 0", name="ck_attendances_subtotal_non_negative"),
        CheckConstraint("discount_total >= 0", name="ck_attendances_discount_total_non_negative"),
        CheckConstraint("surcharge_total >= 0", name="ck_attendances_surcharge_total_non_negative"),
        CheckConstraint("on_call_fee >= 0", name="ck_attendances_on_call_fee_non_negative"),
        CheckConstraint("urgency_fee >= 0", name="ck_attendances_urgency_fee_non_negative"),
        CheckConstraint("clinic_fee >= 0", name="ck_attendances_clinic_fee_non_negative"),
        CheckConstraint("grand_total >= 0", name="ck_attendances_grand_total_non_negative"),
        CheckConstraint(
            "collection_method IN ('HELITO_NICOLAS','INTERNAL','MARLI','COURIER','UBER')",
            name="ck_attendances_collection_method",
        ),
        CheckConstraint(
            "service_level IN ('NORMAL','PLANTAO_NORMAL','PLANTAO_ESPECIAL')",
            name="ck_attendances_service_level",
        ),
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
    collection_method: Mapped[str] = mapped_column(nullable=False, default="INTERNAL")
    service_level: Mapped[str] = mapped_column(nullable=False, default="NORMAL")
    service_date: Mapped[date | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="DRAFT")
    billing_competence: Mapped[date | None] = mapped_column(nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    surcharge_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    on_call_fee: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    is_urgent: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("false")
    )
    urgency_fee: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    clinic_fee: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    fee_lines: Mapped[list[dict[str, str | None]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    grand_total: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    protocol_year: Mapped[int | None] = mapped_column(nullable=True)
    protocol_sequence: Mapped[int | None] = mapped_column(nullable=True)
    protocol_number: Mapped[str | None] = mapped_column(nullable=True)
    monthly_closure_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("monthly_closures.id", ondelete="RESTRICT"), nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(nullable=True)
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
    legacy_source_row_number: Mapped[int | None] = mapped_column(nullable=True)
    legacy_protocol_reference: Mapped[str | None] = mapped_column(nullable=True)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )

    items: Mapped[list[AttendanceExamModel]] = relationship(
        back_populates="attendance", cascade="all, delete-orphan"
    )

    __mapper_args__ = {"version_id_col": row_version}  # noqa: RUF012


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
    components_snapshot: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
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
    UPDATE` in the repository, never `MAX + 1` (`.claude/rules/03-database.md`).
    """

    __tablename__ = "attendance_sequences"

    year: Mapped[int] = mapped_column(primary_key=True)
    last_sequence: Mapped[int] = mapped_column(nullable=False, default=0)


class OnCallFeeSettingModel(Base):
    """`version_id_col=row_version` — same optimistic-concurrency pattern as
    `AttendanceModel` above, so two concurrent edits of the same tier's fee
    can't silently overwrite each other.
    """

    __tablename__ = "on_call_fee_settings"
    __table_args__ = (
        CheckConstraint(
            "service_level IN ('PLANTAO_NORMAL','PLANTAO_ESPECIAL')",
            name="ck_on_call_fee_settings_service_level",
        ),
        CheckConstraint("fee_amount >= 0", name="ck_on_call_fee_settings_fee_amount_non_negative"),
        UniqueConstraint("service_level", name="uq_on_call_fee_settings_service_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    service_level: Mapped[str] = mapped_column(nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(nullable=False)
    schedule_label: Mapped[str] = mapped_column(nullable=False, default="")
    weekdays: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), nullable=False, default=list, server_default="{}"
    )
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
    row_version: Mapped[int] = mapped_column(nullable=False, default=1)

    __mapper_args__ = {"version_id_col": row_version}  # noqa: RUF012


class UrgencyFeeSettingModel(Base):
    """Single-row setting; `version_id_col=row_version` as in `OnCallFeeSettingModel`."""

    __tablename__ = "urgency_fee_settings"
    __table_args__ = (
        CheckConstraint("fee_amount >= 0", name="ck_urgency_fee_settings_fee_amount_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fee_amount: Mapped[Decimal] = mapped_column(nullable=False)
    schedule_label: Mapped[str] = mapped_column(nullable=False, default="")
    weekdays: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), nullable=False, default=list, server_default="{}"
    )
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
    row_version: Mapped[int] = mapped_column(nullable=False, default=1)

    __mapper_args__ = {"version_id_col": row_version}  # noqa: RUF012


class ClinicFeeRuleModel(Base):
    __tablename__ = "clinic_fee_rules"
    __table_args__ = (
        CheckConstraint("fee_amount >= 0", name="ck_clinic_fee_rules_fee_amount_non_negative"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name="ck_clinic_fee_rules_valid_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinics.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(nullable=False)
    valid_from: Mapped[date] = mapped_column(nullable=False)
    valid_to: Mapped[date | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
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

    __mapper_args__ = {"version_id_col": row_version}  # noqa: RUF012
