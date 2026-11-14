"""Visibilidade de um veterinário para o ator (escopo de clínica).

Veterinário é cadastro do laboratório, não de uma clínica. Um ator `CLINIC`
só enxerga autônomos e os vinculados a alguma das suas clínicas — a mesma
regra que `list_page` já aplica na listagem. Fora disso, responde como
"não encontrado" para não revelar a existência do registro.
"""

from __future__ import annotations

from app.modules.veterinarians.domain.entities import Veterinarian
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.authorization import ActorContext
from app.shared.domain.errors import NotFoundError


def ensure_veterinarian_visible(
    actor: ActorContext,
    veterinarian: Veterinarian,
    veterinarians: VeterinarianRepository,
) -> None:
    allowed_clinic_ids = actor.clinic_filter
    if allowed_clinic_ids is None or veterinarian.is_autonomous:
        return
    if not veterinarians.is_linked_to_any_clinic(veterinarian.id, allowed_clinic_ids):
        raise NotFoundError("Veterinário não encontrado.")
