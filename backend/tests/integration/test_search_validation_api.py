"""Integração com PostgreSQL real: texto livre em query string e corpo nunca vira 500.

QA 2026-11-19: `?search=%00` (e NUL em campo de corpo) chegava ao PostgreSQL, que recusa NUL em
texto, e a API respondia 500 em pacientes, veterinários, clínicas, exames, categorias, usuários e
atendimentos (em usuários, a conexão chegou a ser derrubada).
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

SEARCH_ENDPOINTS = [
    "/api/v1/patients",
    "/api/v1/patients/summary",
    "/api/v1/veterinarians",
    "/api/v1/clinics",
    "/api/v1/exams",
    "/api/v1/exam-categories",
    "/api/v1/users",
]


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM audit_log"))
        session.execute(text("DELETE FROM patients"))
        session.execute(text("DELETE FROM veterinarians"))
        session.execute(text("DELETE FROM users"))
        session.commit()


def _search_field_error(response: httpx.Response) -> bool:
    body = response.json()["error"]
    return body["code"] == "VALIDATION_ERROR" and any(
        detail["field"].endswith("search") for detail in body["details"]
    )


@pytest.mark.parametrize("path", SEARCH_ENDPOINTS)
async def test_search_with_a_nul_byte_is_a_422_on_the_search_field(
    admin_client: httpx.AsyncClient, path: str
) -> None:
    response = await admin_client.get(path, params={"search": "a\x00b"})

    assert response.status_code == 422
    assert _search_field_error(response)


@pytest.mark.parametrize("path", SEARCH_ENDPOINTS)
async def test_search_longer_than_the_limit_is_a_422(
    admin_client: httpx.AsyncClient, path: str
) -> None:
    too_long = await admin_client.get(path, params={"search": "x" * 255})
    at_limit = await admin_client.get(path, params={"search": "x" * 254})

    assert too_long.status_code == 422
    assert _search_field_error(too_long)
    assert at_limit.status_code == 200


@pytest.mark.parametrize("path", SEARCH_ENDPOINTS)
async def test_ordinary_search_terms_and_wildcards_still_work(
    admin_client: httpx.AsyncClient, path: str
) -> None:
    for term in ("rex", "%", "_", "joão", "' OR 1=1 --"):
        response = await admin_client.get(path, params={"search": term})
        assert response.status_code == 200, (path, term)


@pytest.mark.parametrize("parameter", ["protocol_number", "owner_name"])
@pytest.mark.parametrize("path", ["/api/v1/attendances", "/api/v1/attendances/status-counts"])
async def test_attendance_text_filters_reject_a_nul_byte(
    admin_client: httpx.AsyncClient, path: str, parameter: str
) -> None:
    response = await admin_client.get(path, params={parameter: "P0\x00"})

    assert response.status_code == 422
    assert any(d["field"].endswith(parameter) for d in response.json()["error"]["details"])


async def test_a_nul_byte_in_a_body_field_is_a_422_not_a_500(
    admin_client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        species_id = session.execute(text("SELECT id FROM species LIMIT 1")).scalar_one()
        clinic_id = session.execute(text("SELECT id FROM clinics LIMIT 1")).scalar_one_or_none()
        if clinic_id is None:
            session.execute(
                text(
                    "INSERT INTO clinics (id, name, status, created_at, updated_at, row_version) "
                    "VALUES (gen_random_uuid(), 'Clínica NUL', 'ACTIVE', now(), now(), 1)"
                )
            )
            session.commit()
            clinic_id = session.execute(text("SELECT id FROM clinics LIMIT 1")).scalar_one()

    patient = await admin_client.post(
        "/api/v1/patients",
        json={
            "clinic_id": str(clinic_id),
            "name": "a\x00b",
            "species_id": str(species_id),
            "sex": "MALE",
            "owner_name": "Maria",
        },
    )
    vet = await admin_client.post(
        "/api/v1/veterinarians",
        json={"name": "Dra. NUL", "crmv": "NUL\x00-1", "is_autonomous": True},
    )

    for response in (patient, vet):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert "\x00" not in response.text


async def test_unlinking_a_clinic_rejects_a_nul_byte_in_the_reason(
    admin_client: httpx.AsyncClient,
) -> None:
    url = f"/api/v1/veterinarians/{uuid4()}/clinics/{uuid4()}"

    nul = await admin_client.request("DELETE", url, params={"reason": "a\x00b"})
    missing = await admin_client.request("DELETE", url)

    assert nul.status_code == 422
    assert any(d["field"].endswith("reason") for d in nul.json()["error"]["details"])
    assert missing.status_code == 422
