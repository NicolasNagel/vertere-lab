"""Close a monthly period for real — Incremento 4.2, `POST /closures`
(`.claude/rules/13-monthly-closure.md`).

Single transactional flow, in the exact order the rule prescribes: advisory
lock by clinic+competence → revalidate no active closure exists → select and
lock the eligible items → recompute totals in the backend (never trust an
old prévia) → build the closure + snapshots → associate the source
attendances → compare the snapshot sum against the header before commit →
audit + outbox. The caller wraps this in a unit of work and an
`Idempotency-Key` guard, same shape as `ConfirmAttendanceUseCase`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.billing.application.dtos import MonthlyClosureDTO
from app.modules.billing.application.mappers import monthly_closure_to_dto
from app.modules.billing.domain.eligibility import is_eligible
from app.modules.billing.domain.entities import (
    ClosureStatus,
    CompetencePeriod,
    MonthlyClosure,
    MonthlyClosureItem,
)
from app.modules.billing.domain.repositories import (
    ClosureCandidateLockRepository,
    MonthlyClosureRepository,
)
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.identity.application.dtos import AuthenticatedUserDTO
from app.shared.application.clock import Clock
from app.shared.domain.errors import (
    ClosureAlreadyExistsError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.shared.domain.money import round_currency
from app.shared.outbox.domain.entities import OutboxEvent
from app.shared.outbox.domain.repositories import OutboxEventRepository

_REQUIRED_PERMISSION = "closures.close"


@dataclass(frozen=True, kw_only=True)
class CloseMonthlyPeriodCommand:
    actor: AuthenticatedUserDTO
    clinic_id: UUID
    year: int
    month: int


class CloseMonthlyPeriodUseCase:
    def __init__(
        self,
        *,
        clinics: ClinicRepository,
        candidates: ClosureCandidateLockRepository,
        closures: MonthlyClosureRepository,
        audit: AuditLogWriter,
        outbox: OutboxEventRepository,
        clock: Clock,
    ) -> None:
        self._clinics = clinics
        self._candidates = candidates
        self._closures = closures
        self._audit = audit
        self._outbox = outbox
        self._clock = clock

    def execute(self, command: CloseMonthlyPeriodCommand) -> MonthlyClosureDTO:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        clinic = self._clinics.get_by_id(command.clinic_id)
        if clinic is None:
            raise NotFoundError("Clínica não encontrada.")

        period = CompetencePeriod(year=command.year, month=command.month)

        # Advisory lock first — everything below, including the
        # "already exists" check, must happen only after this call so two
        # concurrent closes for the same clinic+competence serialize instead
        # of both passing the check (`.claude/rules/03-database.md`).
        self._closures.acquire_active_lock(
            clinic_id=command.clinic_id, year=period.year, month=period.month
        )

        if (
            self._closures.get_active_for_clinic_and_period(
                clinic_id=command.clinic_id, year=period.year, month=period.month
            )
            is not None
        ):
            raise ClosureAlreadyExistsError(
                "Já existe um fechamento ativo para esta clínica e competência."
            )

        locked_candidates = self._candidates.list_candidates_for_update(
            clinic_id=command.clinic_id, period=period
        )
        eligible = [
            candidate for candidate in locked_candidates if is_eligible(candidate, period)[0]
        ]
        if not eligible:
            raise ValidationError("Nenhum item elegível para fechar nesta competência.")

        now = self._clock.now()
        closure_id = uuid4()
        items = [
            MonthlyClosureItem(
                id=uuid4(),
                monthly_closure_id=closure_id,
                attendance_id=candidate.attendance_id,
                attendance_exam_id=candidate.attendance_exam_id,
                protocol_number=candidate.protocol_number,
                patient_name=candidate.patient_name,
                exam_name=candidate.exam_name,
                price_base=candidate.price_base,
                quantity=candidate.quantity,
                discount_amount=candidate.discount_amount,
                surcharge_amount=candidate.surcharge_amount,
                total_amount=candidate.total_amount,
            )
            for candidate in eligible
        ]

        closure = MonthlyClosure(
            id=closure_id,
            clinic_id=command.clinic_id,
            competence_year=period.year,
            competence_month=period.month,
            period_start=period.period_start,
            period_end=period.period_end,
            status=ClosureStatus.CLOSED,
            item_count=len(items),
            subtotal=round_currency(
                sum((item.price_base * item.quantity for item in items), Decimal("0"))
            ),
            discount_total=round_currency(
                sum((item.discount_amount for item in items), Decimal("0"))
            ),
            surcharge_total=round_currency(
                sum((item.surcharge_amount for item in items), Decimal("0"))
            ),
            grand_total=round_currency(sum((item.total_amount for item in items), Decimal("0"))),
            generated_by=command.actor.id,
            closed_by=command.actor.id,
            generated_at=now,
            closed_at=now,
            items=items,
        )

        self._closures.add(closure)
        self._candidates.mark_associated_with_closure(
            attendance_ids={candidate.attendance_id for candidate in eligible},
            closure_id=closure_id,
        )

        # Pre-commit reconciliation (`.claude/rules/13-monthly-closure.md`:
        # "compara soma dos snapshots com o cabeçalho antes do commit") —
        # reads back from `closure.items`, not the local `items` list, so a
        # future refactor that constructs `MonthlyClosure` through a
        # different path still gets caught here.
        reconciled_total = round_currency(
            sum((item.total_amount for item in closure.items), Decimal("0"))
        )
        assert reconciled_total == closure.grand_total, "Soma dos itens diverge do cabeçalho."

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope.LAB,
                action="closures.closed",
                entity_type="monthly_closure",
                entity_id=str(closure_id),
                after_state={
                    "clinic_id": str(command.clinic_id),
                    "competence_year": period.year,
                    "competence_month": period.month,
                    "item_count": closure.item_count,
                    "grand_total": str(closure.grand_total),
                },
            )
        )
        self._outbox.add(
            OutboxEvent(
                event_type="closures.closed",
                payload={
                    "closure_id": str(closure_id),
                    "clinic_id": str(command.clinic_id),
                    "competence_year": period.year,
                    "competence_month": period.month,
                    "grand_total": str(closure.grand_total),
                },
            )
        )

        return monthly_closure_to_dto(closure)
