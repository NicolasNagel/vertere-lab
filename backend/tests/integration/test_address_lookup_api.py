"""Integração via HTTPX/ASGI — autenticação real (PostgreSQL/Testcontainers),
provedor ViaCEP substituído por um fake via dependency override (mock só na
fronteira externa, nunca no que está sendo testado — rule: 09-testing.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.address_lookup.api.dependencies import get_cep_lookup_port
from app.modules.address_lookup.domain.entities import CepAddress
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN
from app.shared.domain.errors import ExternalServiceUnavailableError

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


class _FakeCepLookupPort:
    def __init__(self, *, result: CepAddress | None = None, unavailable: bool = False) -> None:
        self._result = result
        self._unavailable = unavailable

    def lookup(self, cep: str) -> CepAddress | None:
        if self._unavailable:
            raise ExternalServiceUnavailableError("indisponível")
        return self._result


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM audit_log"))
        session.execute(text("DELETE FROM users"))
        session.commit()


def _create_user(
    session_factory: sessionmaker[Session], *, email: str, password: str, role_id: UUID
) -> UserModel:
    with session_factory() as session:
        now = datetime.now(UTC)
        user = UserModel(
            id=uuid4(),
            email=email,
            full_name=email,
            password_hash=hash_password(password),
            is_active=True,
            role_id=role_id,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()
        session.add(LabMembershipModel(id=uuid4(), user_id=user.id, is_active=True, granted_at=now))
        session.commit()
        session.refresh(user)
        return user


async def _login(client: httpx.AsyncClient, *, email: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": email, "password": password, "remember_me": False},
    )
    assert response.status_code == 200


async def test_cep_lookup_requires_session_validates_format_and_maps_provider_outcomes(
    app: FastAPI, client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    assert (await client.get("/api/v1/address-lookup/cep/01310100")).status_code == 401

    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    app.dependency_overrides[get_cep_lookup_port] = lambda: _FakeCepLookupPort(
        result=CepAddress(
            zip_code="01310100",
            street="Avenida Paulista",
            neighborhood="Bela Vista",
            city="São Paulo",
            state="SP",
        )
    )
    found = await client.get("/api/v1/address-lookup/cep/01310-100")
    assert found.status_code == 200
    assert (found.json()["street"], found.json()["city"]) == ("Avenida Paulista", "São Paulo")

    malformed = await client.get("/api/v1/address-lookup/cep/123")
    assert malformed.status_code == 422
    assert malformed.json()["error"]["code"] == "VALIDATION_ERROR"

    app.dependency_overrides[get_cep_lookup_port] = lambda: _FakeCepLookupPort(result=None)
    missing = await client.get("/api/v1/address-lookup/cep/00000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    app.dependency_overrides[get_cep_lookup_port] = lambda: _FakeCepLookupPort(unavailable=True)
    unavailable = await client.get("/api/v1/address-lookup/cep/01310100")
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "EXTERNAL_SERVICE_UNAVAILABLE"
