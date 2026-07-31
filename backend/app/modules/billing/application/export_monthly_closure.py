"""CSV export of a closed competence — Incremento 4.2, `GET /closures/{id}/export`.

Pure formatting function, not a use case (`.claude/rules/03-backend.md`: a
class with one method and no state is over-engineering here) — the router
gets the `MonthlyClosureDTO` from `GetMonthlyClosureUseCase` (same
permission check, same 404 handling) and only then calls this to shape the
response body. Always built from the persisted snapshot passed in, never
re-reads anything (`.claude/rules/13-monthly-closure.md`: "exportação usa o
snapshot, não recalcula no cliente" — same rule, backend side).
"""

from __future__ import annotations

import csv
import io

from app.modules.billing.application.dtos import MonthlyClosureDTO

_HEADER = (
    "protocolo",
    "paciente",
    "exame",
    "preco_base",
    "quantidade",
    "desconto",
    "adicional",
    "total",
)


def monthly_closure_to_csv(closure: MonthlyClosureDTO) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_HEADER)
    for item in closure.items:
        writer.writerow(
            (
                item.protocol_number or "",
                item.patient_name,
                item.exam_name,
                str(item.price_base),
                item.quantity,
                str(item.discount_amount),
                str(item.surcharge_amount),
                str(item.total_amount),
            )
        )
    return buffer.getvalue()
