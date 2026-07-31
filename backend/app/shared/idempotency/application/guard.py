"""Generic Idempotency-Key coordination for critical POSTs (rule:
.claude/rules/02-backend.md — "POST de criação/confirmação/fechamento aceita
Idempotency-Key"; "Mesma chave + mesmo payload → retorna o resultado
anterior. Mesma chave + payload diferente → 409").

Callers call ``begin`` before running their use case and ``complete`` right
after, both inside the same unit-of-work transaction as the business write.
If the use case raises and the transaction rolls back, the IN_PROGRESS
record rolls back with it — a genuinely failed attempt can always be
retried with the same key, only a successfully committed one is replayed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.shared.domain.errors import IdempotencyConflictError
from app.shared.idempotency.domain.entities import IdempotencyRecord, IdempotencyRecordStatus
from app.shared.idempotency.domain.repositories import IdempotencyRecordRepository


def hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, kw_only=True)
class IdempotencyOutcome:
    record_id: UUID
    # Set when this call is a replay of an already-completed request — the
    # caller must skip the use case entirely and return this response as-is.
    replayed_response: tuple[int, dict[str, Any]] | None


class IdempotencyGuard:
    def __init__(self, *, records: IdempotencyRecordRepository) -> None:
        self._records = records

    def begin(
        self,
        *,
        actor_id: UUID,
        operation: str,
        idempotency_key: str,
        payload: Any,
        now: datetime,
    ) -> IdempotencyOutcome:
        payload_hash = hash_payload(payload)
        record_id = uuid4()
        record = IdempotencyRecord(
            id=record_id,
            actor_id=actor_id,
            operation=operation,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            status=IdempotencyRecordStatus.IN_PROGRESS,
            created_at=now,
        )
        if self._records.try_begin(record):
            return IdempotencyOutcome(record_id=record_id, replayed_response=None)

        existing = self._records.find(
            actor_id=actor_id, operation=operation, idempotency_key=idempotency_key
        )
        if existing is None:
            # try_begin reported a collision but the row isn't visible to
            # this same transaction's SELECT — treat as a conflict rather
            # than silently proceeding with a fresh attempt.
            raise IdempotencyConflictError(
                "Não foi possível registrar a requisição idempotente. Tente novamente."
            )
        if existing.status == IdempotencyRecordStatus.IN_PROGRESS:
            raise IdempotencyConflictError(
                "Uma requisição idêntica já está em processamento. Tente novamente em instantes."
            )
        if existing.payload_hash != payload_hash:
            raise IdempotencyConflictError(
                "A mesma Idempotency-Key foi usada com um payload diferente."
            )
        if existing.response_status_code is None or existing.response_body is None:
            raise IdempotencyConflictError(
                "Requisição anterior com esta chave não concluiu com sucesso."
            )
        return IdempotencyOutcome(
            record_id=existing.id,
            replayed_response=(existing.response_status_code, existing.response_body),
        )

    def complete(
        self,
        record_id: UUID,
        *,
        status_code: int,
        body: dict[str, Any],
        now: datetime,
    ) -> None:
        self._records.mark_completed(record_id, status_code=status_code, body=body, now=now)
