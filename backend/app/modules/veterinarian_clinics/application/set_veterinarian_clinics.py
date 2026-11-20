"""Alteração em lote dos vínculos de um veterinário com clínicas.

Uma única chamada aplica adições, remoções e a clínica principal numa só
transação, com um motivo e uma entrada de auditoria. Substitui o fluxo de
"uma clínica por vez" (que com 100 clínicas exigiria 100 requisições e
100 motivos).

Semântica de diff: vincular quem já está vinculado e desvincular quem não
está são no-ops (só importa o estado final). O estado final precisa respeitar
as regras de sempre: veterinário não autônomo exige ao menos uma clínica, e a
clínica principal é uma só e está entre as vinculadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.clinics.domain.entities import ClinicStatus
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.veterinarian_clinics.domain.entities import VeterinarianClinicLink
from app.modules.veterinarian_clinics.domain.errors import LastClinicLinkRequiredError
from app.modules.veterinarian_clinics.domain.repositories import VeterinarianClinicLinkRepository
from app.modules.veterinarians.application.visibility import (
    ensure_veterinarian_linkable,
    ensure_veterinarian_visible,
)
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.authorization import ActorContext
from app.shared.application.clock import Clock
from app.shared.domain.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError

_REQUIRED_PERMISSION = "veterinarians.manage"
MAX_CLINICS_PER_REQUEST = 500


@dataclass(frozen=True, kw_only=True)
class SetVeterinarianClinicsCommand:
    actor: ActorContext
    veterinarian_id: UUID
    add_clinic_ids: tuple[UUID, ...]
    remove_clinic_ids: tuple[UUID, ...]
    primary_clinic_id: UUID | None
    expected_row_version: int
    reason: str


class SetVeterinarianClinicsUseCase:
    def __init__(
        self,
        *,
        veterinarians: VeterinarianRepository,
        clinics: ClinicRepository,
        links: VeterinarianClinicLinkRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._veterinarians = veterinarians
        self._clinics = clinics
        self._links = links
        self._audit = audit
        self._clock = clock

    def execute(self, command: SetVeterinarianClinicsCommand) -> None:
        if _REQUIRED_PERMISSION not in command.actor.permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        reason = command.reason.strip()
        if not reason:
            raise ValidationError("Informe o motivo da alteração.")

        add_ids = command.add_clinic_ids
        remove_ids = command.remove_clinic_ids
        if len(add_ids) > MAX_CLINICS_PER_REQUEST or len(remove_ids) > MAX_CLINICS_PER_REQUEST:
            raise ValidationError(
                f"Altere no máximo {MAX_CLINICS_PER_REQUEST} clínicas por vez para vincular "
                "ou desvincular."
            )
        if len(set(add_ids)) != len(add_ids) or len(set(remove_ids)) != len(remove_ids):
            raise ValidationError("A lista de clínicas tem itens repetidos.")
        if set(add_ids) & set(remove_ids):
            raise ValidationError(
                "Uma clínica não pode ser vinculada e desvinculada ao mesmo tempo."
            )

        veterinarian = self._veterinarians.get_by_id(command.veterinarian_id)
        if veterinarian is None:
            raise NotFoundError("Veterinário não encontrado.")
        ensure_veterinarian_visible(command.actor, veterinarian, self._veterinarians)
        ensure_veterinarian_linkable(command.actor, veterinarian, self._veterinarians)

        if veterinarian.row_version != command.expected_row_version:
            raise ConflictError(
                "Este veterinário foi alterado por outra pessoa. Recarregue e tente de novo."
            )

        for clinic_id in (*add_ids, *remove_ids):
            if not command.actor.can_access_clinic(clinic_id):
                raise NotFoundError("Clínica não encontrada.")

        current = self._links.list_by_veterinarian(veterinarian.id)
        current_by_clinic = {link.clinic_id: link for link in current}
        current_primary = next((link.clinic_id for link in current if link.primary_clinic), None)

        to_add = [clinic_id for clinic_id in add_ids if clinic_id not in current_by_clinic]
        to_remove = [clinic_id for clinic_id in remove_ids if clinic_id in current_by_clinic]

        for clinic_id in to_add:
            clinic = self._clinics.get_by_id(clinic_id)
            if clinic is None:
                raise NotFoundError("Clínica não encontrada.")
            if clinic.status == ClinicStatus.INACTIVE:
                raise ValidationError(
                    f"A clínica {clinic.name} está inativa e não pode ser vinculada."
                )

        final_ids = [
            link.clinic_id for link in current if link.clinic_id not in set(to_remove)
        ] + to_add

        if not veterinarian.is_autonomous and not final_ids:
            raise LastClinicLinkRequiredError(
                "Veterinário não autônomo precisa de ao menos uma clínica vinculada."
            )

        if command.primary_clinic_id is not None and command.primary_clinic_id not in final_ids:
            raise ValidationError("A clínica principal precisa estar entre as clínicas vinculadas.")

        if command.primary_clinic_id is not None:
            new_primary: UUID | None = command.primary_clinic_id
        elif current_primary is not None and current_primary in final_ids:
            new_primary = current_primary
        else:
            new_primary = final_ids[0] if final_ids else None

        if not to_add and not to_remove and new_primary == current_primary:
            return

        before_state = _audit_state(
            [link.clinic_id for link in current], current_primary=current_primary
        )

        now = self._clock.now()
        for clinic_id in to_remove:
            self._links.delete(current_by_clinic[clinic_id])
        self._links.clear_primary_for_veterinarian(veterinarian.id)
        for clinic_id in to_add:
            self._links.add(
                VeterinarianClinicLink(
                    id=uuid4(),
                    veterinarian_id=veterinarian.id,
                    clinic_id=clinic_id,
                    primary_clinic=clinic_id == new_primary,
                    created_by=command.actor.id,
                    created_at=now,
                )
            )
        if new_primary is not None and new_primary in current_by_clinic:
            self._links.mark_primary(current_by_clinic[new_primary].id)

        veterinarian.touch(updated_by=command.actor.id, now=now)
        self._veterinarians.save(veterinarian)

        self._audit.record(
            AuditEntry(
                actor_user_id=command.actor.id,
                actor_scope=ActorScope(command.actor.role_scope),
                action="veterinarian_clinics.batch_updated",
                entity_type="veterinarian",
                entity_id=str(veterinarian.id),
                before_state=before_state,
                after_state=_audit_state(final_ids, current_primary=new_primary),
                reason=reason,
            )
        )


def _audit_state(
    clinic_ids: list[UUID], *, current_primary: UUID | None
) -> dict[str, str | int | list[str] | None]:
    """Só ids e contagens: nenhum dado pessoal vai para a auditoria."""
    return {
        "clinic_count": len(clinic_ids),
        "clinic_ids": sorted(str(clinic_id) for clinic_id in clinic_ids),
        "primary_clinic_id": str(current_primary) if current_primary is not None else None,
    }
