"""Address-lookup API — thin router, no business rule
(rule: .claude/rules/02-backend.md).

Authenticated but not permission-scoped: the data is public and nothing in
the clinic/owner/patient domain is read or written here, so there is no
scope to check — but a session is still required so this never becomes an
open anonymous proxy to a third party.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.modules.address_lookup.api.dependencies import get_cep_lookup_port
from app.modules.address_lookup.api.schemas import CepAddressRead
from app.modules.address_lookup.application.lookup_cep import LookupCepQuery, LookupCepUseCase
from app.modules.address_lookup.application.ports import CepLookupPort
from app.modules.identity.api.dependencies import get_current_user
from app.modules.identity.application.dtos import AuthenticatedUserDTO

logger = logging.getLogger("app.address_lookup")

router = APIRouter(prefix="/address-lookup", tags=["address-lookup"])


@router.get("/cep/{cep}", response_model=CepAddressRead)
def lookup_cep(
    cep: str,
    provider: CepLookupPort = Depends(get_cep_lookup_port),
    current_user: AuthenticatedUserDTO = Depends(get_current_user),
) -> CepAddressRead:
    logger.debug("cep lookup requested", extra={"user_id": str(current_user.id)})
    use_case = LookupCepUseCase(provider=provider)
    result = use_case.execute(LookupCepQuery(cep=cep))
    return CepAddressRead(
        zip_code=result.zip_code,
        street=result.street,
        neighborhood=result.neighborhood,
        city=result.city,
        state=result.state,
    )
