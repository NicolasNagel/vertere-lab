"""Attendances domain entities.

No FastAPI/SQLAlchemy import here (rule: .claude/rules/00-global.md — domain
layer). Mutation happens through named methods, never by callers poking at
fields directly, so invariants stay enforced in one place.

This module now covers the confirmation slice
(`docs/03-modelo-de-dominio.md` §3): `AttendanceExam` items with a snapshot
of catalog price/name, financial header totals, `billing_competence` and a
transactional protocol (`protocol_year`/`protocol_sequence`).
`Idempotency-Key` handling for `/confirm` lives in `app/shared/idempotency`,
one layer above this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.shared.domain.errors import (
    AttendanceAlreadyClosedError,
    InvalidStateTransitionError,
    ValidationError,
)
from app.shared.domain.money import round_currency
from app.shared.domain.protocol_number import format_protocol_number


class AttendanceStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"


class AttendanceExamStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class CollectionMethod(StrEnum):
    HELITO_NICOLAS = "HELITO_NICOLAS"
    INTERNAL = "INTERNAL"
    MARLI = "MARLI"
    COURIER = "COURIER"
    UBER = "UBER"


class ServiceLevel(StrEnum):
    NORMAL = "NORMAL"
    PLANTAO_NORMAL = "PLANTAO_NORMAL"
    PLANTAO_ESPECIAL = "PLANTAO_ESPECIAL"


@dataclass(kw_only=True)
class OnCallFeeSetting:
    """Configurable flat on-call fee for one plantão tier — cobrada uma
    única vez por atendimento inteiro, não por exame (substitui o antigo
    adicional percentual/fixo configurado por exame no catálogo). `NORMAL`
    não tem linha aqui: sua taxa é sempre zero e nunca configurável, só
    `PLANTAO_NORMAL`/`PLANTAO_ESPECIAL` existem como configuração.

    `schedule_label` é um texto livre e informativo (ex.: "Seg-Sáb · 19h às
    07h") — não é aplicado automaticamente por horário, já que
    `service_level` continua sendo escolhido manualmente na criação do
    atendimento (`.claude/rules/12-attendance.md`); serve só de contexto
    para quem preenche o atendimento.
    """

    id: UUID
    service_level: ServiceLevel
    fee_amount: Decimal
    schedule_label: str = ""
    updated_by: UUID | None = None
    updated_at: datetime
    row_version: int = 1

    def __post_init__(self) -> None:
        if self.service_level == ServiceLevel.NORMAL:
            raise ValidationError("NORMAL não tem taxa de plantão configurável.")
        if self.fee_amount < 0:
            raise ValidationError("Valor da taxa de plantão não pode ser negativo.")

    def update(
        self, *, fee_amount: Decimal, schedule_label: str, now: datetime, updated_by: UUID | None
    ) -> None:
        if fee_amount < 0:
            raise ValidationError("Valor da taxa de plantão não pode ser negativo.")
        self.fee_amount = fee_amount
        self.schedule_label = schedule_label
        self.updated_by = updated_by
        self.updated_at = now


@dataclass(kw_only=True)
class UrgencyFeeSetting:
    """Taxa de urgência: valor fixo único, cobrado uma vez por atendimento marcado como
    urgente. Existe uma única linha (semeada pela migration 0041); o valor é editável com
    `pricing.manage`, sempre com motivo e auditoria."""

    id: UUID
    fee_amount: Decimal
    schedule_label: str = ""
    updated_by: UUID | None = None
    updated_at: datetime
    row_version: int = 1

    def __post_init__(self) -> None:
        if self.fee_amount < 0:
            raise ValidationError("Valor da taxa de urgência não pode ser negativo.")

    def update(
        self, *, fee_amount: Decimal, schedule_label: str, now: datetime, updated_by: UUID | None
    ) -> None:
        if fee_amount < 0:
            raise ValidationError("Valor da taxa de urgência não pode ser negativo.")
        self.fee_amount = fee_amount
        self.schedule_label = schedule_label
        self.updated_by = updated_by
        self.updated_at = now


@dataclass(kw_only=True)
class ClinicFeeRule:
    """Taxa personalizada de uma clínica: valor fixo que SOMA ao total do atendimento (nunca
    substitui preço de exame), cobrado uma vez por atendimento e por regra. Vale para a data do
    serviço entre `valid_from` e `valid_to` (inclusive) enquanto `is_active`. Nunca é apagada:
    inativar ou encerrar a vigência."""

    id: UUID
    clinic_id: UUID
    name: str
    fee_amount: Decimal
    valid_from: date
    valid_to: date | None = None
    is_active: bool = True
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1

    def __post_init__(self) -> None:
        self._validate(self.name, self.fee_amount, self.valid_from, self.valid_to)

    @staticmethod
    def _validate(name: str, fee_amount: Decimal, valid_from: date, valid_to: date | None) -> None:
        if not name.strip():
            raise ValidationError("Informe o nome da taxa.")
        if fee_amount < 0:
            raise ValidationError("Valor da taxa não pode ser negativo.")
        if valid_to is not None and valid_to < valid_from:
            raise ValidationError("O fim da vigência não pode ser anterior ao início.")

    def applies_on(self, service_date: date) -> bool:
        return (
            self.is_active
            and self.valid_from <= service_date
            and (self.valid_to is None or service_date <= self.valid_to)
        )

    def update(
        self,
        *,
        name: str,
        fee_amount: Decimal,
        valid_from: date,
        valid_to: date | None,
        is_active: bool,
        now: datetime,
        updated_by: UUID | None,
    ) -> None:
        self._validate(name, fee_amount, valid_from, valid_to)
        self.name = name.strip()
        self.fee_amount = fee_amount
        self.valid_from = valid_from
        self.valid_to = valid_to
        self.is_active = is_active
        self.updated_by = updated_by
        self.updated_at = now


class FeeKind(StrEnum):
    PLANTAO = "PLANTAO"
    URGENCIA = "URGENCIA"
    CLINICA = "CLINICA"


@dataclass(frozen=True)
class FeeLine:
    """One fee charged on the whole attendance, frozen on it (snapshot)."""

    kind: FeeKind
    label: str
    amount: Decimal
    rule_id: UUID | None = None


@dataclass(frozen=True)
class AttendanceFees:
    """Every flat per-attendance fee resolved by the application layer (the domain does no
    I/O): plantão + urgência + clínica. They always add up."""

    on_call: Decimal = Decimal("0")
    urgency: Decimal = Decimal("0")
    clinic: Decimal = Decimal("0")
    lines: tuple[FeeLine, ...] = ()

    @property
    def total(self) -> Decimal:
        return self.on_call + self.urgency + self.clinic


@dataclass(frozen=True)
class ExamComponentSnapshot:
    """One exam inside a panel (pacote), frozen when the panel was added to the attendance."""

    code: str
    name: str


@dataclass(kw_only=True)
class AttendanceExam:
    """An exam item snapshotted onto a confirmed attendance.

    `exam_code`/`exam_name`/`price_base` are a snapshot taken at
    confirmation time — never re-read from the catalog afterwards
    (`.claude/rules/12-attendance.md`: "atualização da tabela de preço vigente
    nunca altera um snapshot já persistido"). `total_amount` is always
    derived here, never accepted from a caller (rule: "total sempre
    calculado no backend").
    """

    id: UUID
    attendance_id: UUID
    exam_id: UUID
    exam_code: str
    exam_name: str
    price_base: Decimal
    components: tuple[ExamComponentSnapshot, ...] = ()
    quantity: int = 1
    discount_amount: Decimal = Decimal("0")
    surcharge_amount: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    override_reason: str | None = None
    override_by: UUID | None = None
    status: AttendanceExamStatus = AttendanceExamStatus.ACTIVE

    def __post_init__(self) -> None:
        self._recalculate()

    def _recalculate(self) -> None:
        if self.quantity <= 0:
            raise ValidationError("Quantidade do item deve ser maior que zero.")
        if self.discount_amount < 0 or self.surcharge_amount < 0:
            raise ValidationError("Desconto e adicional do item não podem ser negativos.")
        self.total_amount = round_currency(
            self.price_base * self.quantity - self.discount_amount + self.surcharge_amount
        )
        if self.total_amount < 0:
            raise ValidationError("Total do item não pode ser negativo.")

    def revise(
        self,
        *,
        quantity: int,
        discount_amount: Decimal,
        override_reason: str | None,
        override_by: UUID | None,
        status: AttendanceExamStatus,
    ) -> None:
        """Correct quantity/discount/status of a snapshotted item. The price snapshot
        (`price_base`, name, composition) is never touched — only what the lab
        decided for this attendance can change."""
        self.quantity = quantity
        self.discount_amount = discount_amount
        self.override_reason = override_reason
        self.override_by = override_by
        self.status = status
        self._recalculate()


@dataclass(frozen=True, kw_only=True)
class AttendanceTotals:
    subtotal: Decimal
    discount_total: Decimal
    surcharge_total: Decimal
    on_call_fee: Decimal
    urgency_fee: Decimal
    clinic_fee: Decimal
    grand_total: Decimal


def compute_attendance_totals(
    items: list[AttendanceExam],
    *,
    on_call_fee: Decimal = Decimal("0"),
    urgency_fee: Decimal = Decimal("0"),
    clinic_fee: Decimal = Decimal("0"),
) -> AttendanceTotals:
    """Single point of money math for a set of items (rule:
    .claude/rules/12-attendance.md — "moeda e arredondamento centralizados em
    um único ponto do domínio"). Used by `AttendanceRecord.confirm()` and,
    unchanged, by the preview (dry-run) use case — a preview must never be
    able to compute a different total than what confirming would charge.

    `on_call_fee` (resolved by the caller from `OnCallFeeSetting` — domain
    itself has no I/O to look it up) is the one amount that isn't itemized —
    it belongs to the attendance as a whole (a dispatch/on-call fee, not
    tied to any single exam), so it's added on top of the items' total
    rather than folded into `surcharge_total`, which stays a pure sum of
    item-level surcharges.
    """
    if not items:
        raise ValidationError("Confirmação exige ao menos um item de exame.")
    items_total = round_currency(sum((i.total_amount for i in items), Decimal("0")))
    return AttendanceTotals(
        subtotal=round_currency(sum((i.price_base * i.quantity for i in items), Decimal("0"))),
        discount_total=round_currency(sum((i.discount_amount for i in items), Decimal("0"))),
        surcharge_total=round_currency(sum((i.surcharge_amount for i in items), Decimal("0"))),
        on_call_fee=on_call_fee,
        urgency_fee=urgency_fee,
        clinic_fee=clinic_fee,
        grand_total=round_currency(items_total + on_call_fee + urgency_fee + clinic_fee),
    )


@dataclass(kw_only=True)
class AttendanceRecord:
    id: UUID
    clinic_id: UUID
    veterinarian_id: UUID
    patient_id: UUID
    collection_method: CollectionMethod = CollectionMethod.INTERNAL
    service_level: ServiceLevel = ServiceLevel.NORMAL
    service_date: date | None = None
    notes: str | None = None
    status: AttendanceStatus = AttendanceStatus.DRAFT
    items: list[AttendanceExam] = field(default_factory=list)
    billing_competence: date | None = None
    subtotal: Decimal = Decimal("0")
    discount_total: Decimal = Decimal("0")
    surcharge_total: Decimal = Decimal("0")
    on_call_fee: Decimal = Decimal("0")
    is_urgent: bool = False
    urgency_fee: Decimal = Decimal("0")
    clinic_fee: Decimal = Decimal("0")
    fee_lines: tuple[FeeLine, ...] = ()
    grand_total: Decimal = Decimal("0")
    protocol_year: int | None = None
    protocol_sequence: int | None = None
    protocol_number: str | None = None
    # None until Incremento 4.2 associates this attendance with a real
    # closure — the field exists from this slice on because "item já em
    # fechamento é imutável" is a structural invariant the confirmation
    # slice must already respect (docs/03-modelo-de-dominio.md §6).
    monthly_closure_id: UUID | None = None
    cancel_reason: str | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    row_version: int = 1
    # Só preenchidos em atendimentos migrados da planilha legada (Fase 4,
    # `.claude/rules/10-data-migration.md`) — `None` em todo atendimento
    # criado pelo fluxo normal de confirmação.
    legacy_source_row_number: int | None = None
    legacy_protocol_reference: str | None = None
    import_batch_id: UUID | None = None

    @classmethod
    def create_from_legacy_import(
        cls,
        *,
        id: UUID,
        clinic_id: UUID,
        veterinarian_id: UUID,
        patient_id: UUID,
        collection_method: CollectionMethod,
        service_level: ServiceLevel,
        service_date: date,
        items: list[AttendanceExam],
        protocol_year: int,
        protocol_sequence: int,
        on_call_fee: Decimal,
        legacy_source_row_number: int,
        legacy_protocol_reference: str | None,
        import_batch_id: UUID,
        now: datetime,
        created_by: UUID | None,
    ) -> AttendanceRecord:
        """A migrated row never passed through `DRAFT` — there is no prior
        instance to call `.confirm()` on, so this is a factory, not a state
        transition. It reuses `compute_attendance_totals` (the same single
        point of money math `.confirm()` uses) so a migrated attendance can
        never disagree with a live one on how a total is derived from its
        items (`.claude/rules/12-attendance.md`: "moeda e arredondamento
        centralizados em um único ponto do domínio").

        Lands directly in `COMPLETED`, never `CONFIRMED` — historical data
        has nothing left to do, and `update_fields()`/`cancel()` already
        refuse any status outside `(DRAFT, CONFIRMED)`, which gives migrated
        records the same "não pode ser editado" protection a closed
        attendance gets, with no extra guard needed here.
        """
        totals = compute_attendance_totals(items, on_call_fee=on_call_fee)
        return cls(
            id=id,
            clinic_id=clinic_id,
            veterinarian_id=veterinarian_id,
            patient_id=patient_id,
            collection_method=collection_method,
            service_level=service_level,
            service_date=service_date,
            status=AttendanceStatus.COMPLETED,
            items=items,
            billing_competence=service_date.replace(day=1),
            subtotal=totals.subtotal,
            discount_total=totals.discount_total,
            surcharge_total=totals.surcharge_total,
            on_call_fee=totals.on_call_fee,
            grand_total=totals.grand_total,
            protocol_year=protocol_year,
            protocol_sequence=protocol_sequence,
            protocol_number=format_protocol_number(year=protocol_year, sequence=protocol_sequence),
            legacy_source_row_number=legacy_source_row_number,
            legacy_protocol_reference=legacy_protocol_reference,
            import_batch_id=import_batch_id,
            created_by=created_by,
            updated_by=created_by,
            created_at=now,
            updated_at=now,
        )

    def confirm(
        self,
        *,
        items: list[AttendanceExam],
        protocol_year: int,
        protocol_sequence: int,
        on_call_fee: Decimal,
        urgency_fee: Decimal = Decimal("0"),
        clinic_fee: Decimal = Decimal("0"),
        fee_lines: tuple[FeeLine, ...] = (),
        now: datetime,
        confirmed_by: UUID | None,
    ) -> None:
        if self.status != AttendanceStatus.DRAFT:
            raise InvalidStateTransitionError("Atendimento não está em rascunho.")
        if self.service_date is None:
            raise ValidationError("Data do atendimento é obrigatória para confirmar.")

        totals = compute_attendance_totals(
            items, on_call_fee=on_call_fee, urgency_fee=urgency_fee, clinic_fee=clinic_fee
        )

        self.items = items
        self.subtotal = totals.subtotal
        self.discount_total = totals.discount_total
        self.surcharge_total = totals.surcharge_total
        self.on_call_fee = totals.on_call_fee
        self.urgency_fee = totals.urgency_fee
        self.clinic_fee = totals.clinic_fee
        self.fee_lines = fee_lines
        self.grand_total = totals.grand_total
        self.protocol_year = protocol_year
        self.protocol_sequence = protocol_sequence
        self.protocol_number = format_protocol_number(
            year=protocol_year, sequence=protocol_sequence
        )
        self.billing_competence = self.service_date.replace(day=1)
        self.status = AttendanceStatus.CONFIRMED
        self.updated_by = confirmed_by
        self.updated_at = now

    def cancel(self, *, reason: str, now: datetime, cancelled_by: UUID | None) -> None:
        """Cancel exige motivo (`.claude/rules/12-attendance.md`) and is
        allowed from DRAFT or CONFIRMED only — a closed item is immutable
        financially with no code-path shortcut (`.claude/rules/12-attendance.md`:
        "item já em fechamento é imutável financeiramente — sem exceção via
        atalho de código"), enforced here by `monthly_closure_id` even
        though Incremento 4.2 (closing for real) hasn't shipped yet.
        """
        if self.status not in (AttendanceStatus.DRAFT, AttendanceStatus.CONFIRMED):
            raise InvalidStateTransitionError("Atendimento não pode ser cancelado neste estado.")
        if self.monthly_closure_id is not None:
            raise AttendanceAlreadyClosedError(
                "Atendimento pertence a um fechamento e não pode ser cancelado diretamente."
            )

        self.status = AttendanceStatus.CANCELLED
        self.cancel_reason = reason
        self.updated_by = cancelled_by
        self.updated_at = now

    def apply_item_changes(
        self,
        *,
        items: list[AttendanceExam],
        now: datetime,
        updated_by: UUID | None,
        closed_correction: bool = False,
    ) -> None:
        """Replace the item set (removed items stay as `CANCELLED`) and recompute every
        total from the ACTIVE ones. Allowed in `CONFIRMED` and `CANCELLED`; an attendance
        inside a closure only with `closed_correction=True`, and then the caller settles the
        difference as a financial adjustment on that closure."""
        if self.status not in (AttendanceStatus.CONFIRMED, AttendanceStatus.CANCELLED):
            raise InvalidStateTransitionError("Exames não podem ser editados neste estado.")
        if self.monthly_closure_id is not None and not closed_correction:
            raise AttendanceAlreadyClosedError(
                "Atendimento pertence a um fechamento e não pode ser editado diretamente."
            )
        active = [item for item in items if item.status == AttendanceExamStatus.ACTIVE]
        totals = compute_attendance_totals(
            active,
            on_call_fee=self.on_call_fee,
            urgency_fee=self.urgency_fee,
            clinic_fee=self.clinic_fee,
        )
        self.items = items
        self.subtotal = totals.subtotal
        self.discount_total = totals.discount_total
        self.surcharge_total = totals.surcharge_total
        self.grand_total = totals.grand_total
        self.updated_by = updated_by
        self.updated_at = now

    def update_fields(
        self,
        *,
        clinic_id: UUID | None,
        veterinarian_id: UUID | None,
        patient_id: UUID | None,
        collection_method: CollectionMethod | None = None,
        service_level: ServiceLevel | None = None,
        is_urgent: bool | None = None,
        service_date: date | None,
        notes: str | None,
        on_call_fee: Decimal | None = None,
        closed_correction: bool = False,
        now: datetime,
        updated_by: UUID | None,
    ) -> dict[str, tuple[str | None, str | None]]:
        """Controlled edit (`.claude/rules/12-attendance.md`). Any header field can be
        corrected in `DRAFT`, `CONFIRMED` and `CANCELLED` — a wrong clinic, veterinarian,
        date or service level is a correction, not a new fact. What stays blocked is an
        attendance already inside a closure (`monthly_closure_id`): correcting it needs a
        financial adjustment on that closure, a separate use case. Legacy-imported
        (`COMPLETED`) records are never edited here.

        After the draft stage the money fields that depend on the header follow it:
        changing `service_level` recomputes the on-call fee and the grand total (the caller
        resolves `on_call_fee` from the settings, because the domain does no I/O), and
        changing `service_date` moves `billing_competence`. Item prices are snapshots and do
        not change with the date. A `None` argument means "not provided" for every field,
        `notes` included — there is no way to clear notes back to empty via PATCH, only to
        overwrite them.

        Returns only the fields that actually changed, as `{field: (before, after)}`, for
        the audit diff — a caller that gets an empty dict back made a no-op call and should
        skip persisting.
        """
        if self.status not in (
            AttendanceStatus.DRAFT,
            AttendanceStatus.CONFIRMED,
            AttendanceStatus.CANCELLED,
        ):
            raise InvalidStateTransitionError("Atendimento não pode ser editado neste estado.")
        if self.monthly_closure_id is not None and not closed_correction:
            raise AttendanceAlreadyClosedError(
                "Atendimento pertence a um fechamento e não pode ser editado diretamente."
            )

        is_draft = self.status == AttendanceStatus.DRAFT
        changes: dict[str, tuple[str | None, str | None]] = {}
        if clinic_id is not None and clinic_id != self.clinic_id:
            changes["clinic_id"] = (str(self.clinic_id), str(clinic_id))
            self.clinic_id = clinic_id
        if veterinarian_id is not None and veterinarian_id != self.veterinarian_id:
            changes["veterinarian_id"] = (str(self.veterinarian_id), str(veterinarian_id))
            self.veterinarian_id = veterinarian_id
        if patient_id is not None and patient_id != self.patient_id:
            changes["patient_id"] = (str(self.patient_id), str(patient_id))
            self.patient_id = patient_id
        if collection_method is not None and collection_method != self.collection_method:
            changes["collection_method"] = (self.collection_method.value, collection_method.value)
            self.collection_method = collection_method
        if service_level is not None and service_level != self.service_level:
            changes["service_level"] = (self.service_level.value, service_level.value)
            self.service_level = service_level
            if not is_draft:
                if on_call_fee is None:
                    raise ValidationError("Taxa de plantão não informada para o novo tipo.")
                changes["on_call_fee"] = (str(self.on_call_fee), str(on_call_fee))
                previous_total = self.grand_total
                self.on_call_fee = on_call_fee
                self.grand_total = round_currency(
                    sum(
                        (
                            item.total_amount
                            for item in self.items
                            if item.status == AttendanceExamStatus.ACTIVE
                        ),
                        Decimal("0"),
                    )
                    + on_call_fee
                    + self.urgency_fee
                    + self.clinic_fee
                )
                changes["grand_total"] = (str(previous_total), str(self.grand_total))
        if is_urgent is not None and is_urgent != self.is_urgent:
            changes["is_urgent"] = (str(self.is_urgent), str(is_urgent))
            self.is_urgent = is_urgent
        if service_date is not None and service_date != self.service_date:
            changes["service_date"] = (str(self.service_date), str(service_date))
            self.service_date = service_date
            if not is_draft:
                new_competence = service_date.replace(day=1)
                changes["billing_competence"] = (
                    str(self.billing_competence),
                    str(new_competence),
                )
                self.billing_competence = new_competence
        if notes is not None and notes != self.notes:
            changes["notes"] = (self.notes, notes)
            self.notes = notes

        if changes:
            self.updated_by = updated_by
            self.updated_at = now
        return changes

    def reprice_fees(
        self,
        *,
        fees: AttendanceFees,
        changes: dict[str, tuple[str | None, str | None]],
        now: datetime,
        updated_by: UUID | None,
    ) -> None:
        """Re-resolve every per-attendance fee after an edit that can change them (service
        level, urgency, clinic or service date) on an already-priced attendance. Puts the
        fee/total differences into `changes` (the audit diff) and recomputes `grand_total` from
        the ACTIVE items plus the new fees."""
        previous_total = self.grand_total
        previous_fees = (self.on_call_fee, self.urgency_fee, self.clinic_fee)
        self.on_call_fee = fees.on_call
        self.urgency_fee = fees.urgency
        self.clinic_fee = fees.clinic
        self.fee_lines = fees.lines
        active = [item for item in self.items if item.status == AttendanceExamStatus.ACTIVE]
        items_total = round_currency(sum((i.total_amount for i in active), Decimal("0")))
        self.grand_total = round_currency(items_total + fees.total)
        for name, before, after in (
            ("on_call_fee", previous_fees[0], self.on_call_fee),
            ("urgency_fee", previous_fees[1], self.urgency_fee),
            ("clinic_fee", previous_fees[2], self.clinic_fee),
            ("grand_total", previous_total, self.grand_total),
        ):
            # `update_fields` may already have recorded part of the diff (plantão level):
            # keep its original "before" and only move the "after".
            original_before = changes[name][0] if name in changes else str(before)
            if original_before != str(after):
                changes[name] = (original_before, str(after))
            else:
                changes.pop(name, None)
        if changes:
            self.updated_by = updated_by
            self.updated_at = now
