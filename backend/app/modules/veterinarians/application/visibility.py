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
from app.shared.domain.errors import ForbiddenError, NotFoundError


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


def ensure_veterinarian_mutable(
    actor: ActorContext,
    veterinarian: Veterinarian,
    veterinarians: VeterinarianRepository,
) -> None:
    """A clinic actor changes a veterinarian only when every link belongs to its own clinics.

    The record is shared laboratory data: editing or deactivating one that another clinic (or
    nobody) also uses would change that clinic's data. Visible but not owned answers 403, since
    the actor already sees the record. Laboratory actors are unrestricted.
    """
    allowed = actor.clinic_filter
    if allowed is None:
        return
    linked = veterinarians.linked_clinic_ids(veterinarian.id)
    if not linked or not linked <= allowed:
        raise ForbiddenError(
            "Este veterinário é compartilhado com outras clínicas ou sem vínculo; "
            "apenas o laboratório pode alterá-lo."
        )


def ensure_veterinarian_linkable(
    actor: ActorContext,
    veterinarian: Veterinarian,
    veterinarians: VeterinarianRepository,
) -> None:
    """A clinic actor does not adopt a veterinarian that has no clinic yet.

    Linking an unowned autonomous veterinarian to its own clinic would make the actor its sole
    owner and let it rename or deactivate a laboratory record other clinics rely on.
    """
    if actor.clinic_filter is None:
        return
    if not veterinarians.linked_clinic_ids(veterinarian.id):
        raise ForbiddenError(
            "Este veterinário não tem nenhuma clínica vinculada (por exemplo, o último vínculo foi removido); apenas o laboratório pode vinculá-lo de novo."
        )
