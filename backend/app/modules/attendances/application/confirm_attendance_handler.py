"""Atomic orchestration for attendance confirmation."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from uuid import UUID

from app.modules.attendances.application.confirm_attendance import (
    ConfirmAttendanceCommand,
    ConfirmAttendanceUseCase,
)
from app.modules.attendances.application.dtos import AttendanceDTO
from app.modules.attendances.application.mappers import attendance_to_dto
from app.modules.attendances.application.uow import AttendanceUnitOfWork
from app.shared.application.clock import Clock
from app.shared.domain.errors import NotFoundError
from app.shared.idempotency.application.guard import IdempotencyGuard


class ConfirmAttendanceHandler:
    def __init__(self, *, uow: AttendanceUnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, command: ConfirmAttendanceCommand, *, idempotency_key: str) -> AttendanceDTO:
        with self._uow:
            guard = IdempotencyGuard(records=self._uow.idempotency_records)
            outcome = guard.begin(
                actor_id=command.actor.id,
                operation=(
                    f"attendances.confirm:{command.attendance_id}:"
                    f"access-version:{command.actor.row_version}"
                ),
                idempotency_key=idempotency_key,
                payload=_idempotency_payload(command),
                now=self._clock.now(),
            )
            if outcome.replayed_response is not None:
                _, body = outcome.replayed_response
                result = self._load_replayed_attendance(body)
                self._uow.commit()
                return result

            result = ConfirmAttendanceUseCase(
                attendances=self._uow.attendances,
                attendance_sequences=self._uow.attendance_sequences,
                clinics=self._uow.clinics,
                veterinarians=self._uow.veterinarians,
                veterinarian_clinics=self._uow.veterinarian_clinics,
                patients=self._uow.patients,
                exams=self._uow.exams,
                on_call_fees=self._uow.on_call_fees,
                urgency_fee=self._uow.urgency_fee,
                clinic_fee_rules=self._uow.clinic_fee_rules,
                audit=self._uow.audit,
                clock=self._clock,
            ).execute(command)
            guard.complete(
                outcome.record_id,
                status_code=200,
                body=_replay_snapshot(result),
                now=self._clock.now(),
            )
            self._uow.commit()
            return result

    def _load_replayed_attendance(self, body: dict[str, object]) -> AttendanceDTO:
        try:
            attendance_id = UUID(str(body["id"]))
        except (KeyError, ValueError) as exc:
            raise NotFoundError("Resultado idempotente do atendimento não encontrado.") from exc
        attendance = self._uow.attendances.get_by_id(attendance_id)
        if attendance is None:
            raise NotFoundError("Resultado idempotente do atendimento não encontrado.")
        result = attendance_to_dto(attendance)
        decimals = body.get("decimals")
        item_decimals = body.get("item_decimals")
        if not isinstance(decimals, dict) or not isinstance(item_decimals, dict):
            return result
        return replace(
            result,
            subtotal=Decimal(str(decimals["subtotal"])),
            discount_total=Decimal(str(decimals["discount_total"])),
            surcharge_total=Decimal(str(decimals["surcharge_total"])),
            on_call_fee=Decimal(str(decimals["on_call_fee"])),
            urgency_fee=Decimal(str(decimals.get("urgency_fee", result.urgency_fee))),
            clinic_fee=Decimal(str(decimals.get("clinic_fee", result.clinic_fee))),
            grand_total=Decimal(str(decimals["grand_total"])),
            items=[
                replace(
                    item,
                    price_base=Decimal(str(item_decimals[str(item.id)]["price_base"])),
                    discount_amount=Decimal(str(item_decimals[str(item.id)]["discount_amount"])),
                    surcharge_amount=Decimal(str(item_decimals[str(item.id)]["surcharge_amount"])),
                    total_amount=Decimal(str(item_decimals[str(item.id)]["total_amount"])),
                )
                for item in result.items
            ],
        )


def _idempotency_payload(command: ConfirmAttendanceCommand) -> dict[str, object]:
    return {
        "items": [
            {
                "exam_id": str(item.exam_id),
                "quantity": item.quantity,
                "discount_amount": (
                    str(item.discount_amount) if item.discount_amount is not None else None
                ),
                "override_reason": item.override_reason,
            }
            for item in command.items
        ]
    }


def _replay_snapshot(result: AttendanceDTO) -> dict[str, object]:
    return {
        "id": str(result.id),
        "decimals": {
            "subtotal": str(result.subtotal),
            "discount_total": str(result.discount_total),
            "surcharge_total": str(result.surcharge_total),
            "on_call_fee": str(result.on_call_fee),
            "urgency_fee": str(result.urgency_fee),
            "clinic_fee": str(result.clinic_fee),
            "grand_total": str(result.grand_total),
        },
        "item_decimals": {
            str(item.id): {
                "price_base": str(item.price_base),
                "discount_amount": str(item.discount_amount),
                "surcharge_amount": str(item.surcharge_amount),
                "total_amount": str(item.total_amount),
            }
            for item in result.items
        },
    }
