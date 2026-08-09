"""Single source of truth for closure item eligibility.

`.claude/rules/13-monthly-closure.md`: "usa a mesma regra de elegibilidade do
fechamento de verdade (nunca uma versão simplificada que depois diverge)".
Incremento 4.2 (fechar de fato) must reuse this exact function — never
reimplement the rule.
"""

from __future__ import annotations

from app.modules.billing.domain.entities import ClosureCandidateItem, CompetencePeriod

_CANCELLED = "CANCELLED"


def is_eligible(item: ClosureCandidateItem, period: CompetencePeriod) -> tuple[bool, str | None]:
    if item.service_date is None or not (
        period.period_start <= item.service_date <= period.period_end
    ):
        return False, "Atendimento fora do período selecionado."
    if item.attendance_status == _CANCELLED:
        return False, "Atendimento cancelado."
    if item.item_status == _CANCELLED:
        return False, "Item de exame cancelado."
    if item.monthly_closure_id is not None:
        return False, "Item já pertence a outro fechamento ativo."
    if item.total_amount < 0:
        return False, "Valor financeiro do item é inválido."
    return True, None
