"""Pydantic schema for the address-lookup API — read-only, no create/update."""

from __future__ import annotations

from pydantic import BaseModel


class CepAddressRead(BaseModel):
    zip_code: str
    street: str | None
    neighborhood: str | None
    city: str | None
    state: str | None
