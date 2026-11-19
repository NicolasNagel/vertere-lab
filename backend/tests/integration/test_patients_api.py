"""Integração com PostgreSQL real (Testcontainers) — catálogo de espécies
seedado pela migration 0007 e CRUD de pacientes (owner embutido), ponta a
ponta via HTTPX/ASGI.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_FINANCE, ROLE_LAB_ADMIN, ROLE_RECEPTION

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM audit_log"))
        session.execute(text("DELETE FROM patients"))
        session.execute(text("DELETE FROM users"))
        session.commit()


def _get_species_id(session_factory: sessionmaker[Session], *, name: str) -> str:
    with session_factory() as session:
        row = session.execute(
            text("SELECT id FROM species WHERE name = :name"), {"name": name}
        ).one()
        return str(row[0])


def _clinic_id(session_factory: sessionmaker[Session]) -> str:
    with session_factory() as session:
        existing = session.execute(text("SELECT id FROM clinics LIMIT 1")).scalar_one_or_none()
        if existing is not None:
            return str(existing)
        clinic_id = uuid4()
        session.execute(
            text(
                "INSERT INTO clinics (id, name, status, created_at, updated_at, row_version) "
                "VALUES (:id, :name, 'ACTIVE', now(), now(), 1)"
            ),
            {"id": clinic_id, "name": "Clínica de Teste"},
        )
        session.commit()
        return str(clinic_id)


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


async def _login_as(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, email: str, role_id: UUID
) -> None:
    _create_user(session_factory, email=email, password="s3nhaForte!", role_id=role_id)
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": email, "password": "s3nhaForte!", "remember_me": False},
    )
    assert response.status_code == 200


async def test_species_are_readable_by_any_authenticated_role_and_seeded(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Species has no dedicated permission — any authenticated user can read
    it (the Exam catalog also needs it, possibly for a pure `FINANCE`)."""
    assert (await client.get("/api/v1/species")).status_code == 401

    await _login_as(client, session_factory, email="finance@vertere.local", role_id=ROLE_FINANCE)
    assert (await client.get("/api/v1/species")).status_code == 200

    await _login_as(
        client, session_factory, email="reception@vertere.local", role_id=ROLE_RECEPTION
    )
    response = await client.get("/api/v1/species")
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == sorted(names)
    assert {"Canino", "Felino", "Bovino", "Equino", "Coelho", "Caprino"} <= set(names)


async def test_patient_crud_permissions_validation_versions_deactivation_and_search(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    dog_id = _get_species_id(session_factory, name="Canino")
    cat_id = _get_species_id(session_factory, name="Felino")
    clinic_id = _clinic_id(session_factory)

    def payload(name: str, owner: str, species_id: str = dog_id, **extra: str) -> dict[str, str]:
        return {
            "clinic_id": clinic_id,
            "name": name,
            "species_id": species_id,
            "sex": "MALE",
            "owner_name": owner,
            **extra,
        }

    # Sem permissão de pacientes (financeiro) a criação é negada.
    await _login_as(client, session_factory, email="finance@vertere.local", role_id=ROLE_FINANCE)
    denied = await client.post("/api/v1/patients", json=payload("Rex", "Maria Souza"))
    assert denied.status_code == 403

    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)

    # Criação com owner embutido e leitura por id.
    created = await client.post(
        "/api/v1/patients",
        json={
            **payload("Mimi", "Joana Lima", cat_id, breed="Siamês"),
            "sex": "FEMALE",
            "age_description": "3 anos",
            "owner_phone": "(47) 9 9914-6833",
        },
    )
    assert created.status_code == 201
    mimi = created.json()
    assert (mimi["name"], mimi["owner_name"], mimi["status"]) == ("Mimi", "Joana Lima", "ACTIVE")
    fetched = await client.get(f"/api/v1/patients/{mimi['id']}")
    assert (fetched.status_code, fetched.json()["owner_name"]) == (200, "Joana Lima")

    # Espécie inexistente é 404 (validada antes do FK), nunca 500.
    unknown = await client.post(
        "/api/v1/patients", json=payload("Rex", "Maria Souza", str(uuid4()))
    )
    assert unknown.status_code == 404

    # Mesmo nome de tutor é permitido em pacientes distintos.
    first = await client.post("/api/v1/patients", json=payload("Rex", "Maria Souza"))
    second = await client.post("/api/v1/patients", json=payload("Rex II", "Maria Souza"))
    assert (first.status_code, second.status_code) == (201, 201)
    rex = first.json()

    # Versão errada conflita; versões encadeadas usam a devolvida pela edição anterior.
    base = {"species_id": dog_id, "sex": "MALE", "owner_name": "Maria Souza", "status": "ACTIVE"}
    url = f"/api/v1/patients/{rex['id']}"
    stale = await client.patch(
        url, json={**base, "name": "Rex Atualizado", "expected_row_version": rex["row_version"] + 1}
    )
    assert stale.status_code == 409
    versions = [rex["row_version"]]
    for name in ("Rex Um", "Rex Dois"):
        update = await client.patch(
            url, json={**base, "name": name, "expected_row_version": versions[-1]}
        )
        assert update.status_code == 200
        versions.append(update.json()["row_version"])
    assert versions == [rex["row_version"], rex["row_version"] + 1, rex["row_version"] + 2]

    # Desativar preserva o registro.
    deactivated = await client.post(f"{url}/deactivate")
    assert deactivated.status_code == 200
    assert (deactivated.json()["status"], deactivated.json()["name"]) == ("INACTIVE", "Rex Dois")

    # Busca por tutor; `%` e `_` digitados são texto literal, não curinga de LIKE.
    joana = await client.get("/api/v1/patients", params={"search": "joana"})
    assert joana.status_code == 200
    assert [item["name"] for item in joana.json()["items"]] == ["Mimi"]
    for wildcard in ("%", "_", "%%%%"):
        literal = await client.get("/api/v1/patients", params={"search": wildcard})
        assert literal.status_code == 200
        assert literal.json()["total"] == 0, wildcard
    await client.post("/api/v1/patients", json=payload("Mel", "Ana 100%_Pet"))
    literal_match = await client.get("/api/v1/patients", params={"search": "100%_pet"})
    assert [item["name"] for item in literal_match.json()["items"]] == ["Mel"]


async def test_patient_structured_age_round_trips_validates_pair_and_tracks_recorded_date(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    dog_id = _get_species_id(session_factory, name="Canino")
    clinic_id = _clinic_id(session_factory)
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    base = {
        "clinic_id": clinic_id,
        "name": "Thor",
        "species_id": dog_id,
        "sex": "MALE",
        "owner_name": "Carla Dias",
    }

    created = await client.post(
        "/api/v1/patients", json={**base, "age_value": 8, "age_unit": "MONTHS"}
    )
    assert created.status_code == 201
    thor = created.json()
    assert (thor["age_value"], thor["age_unit"]) == (8, "MONTHS")
    assert thor["age_description"] == "8 meses"
    assert thor["age_recorded_on"] == datetime.now(UTC).date().isoformat()

    # Só valor ou só unidade, unidade desconhecida e valor fora do intervalo: 422, nunca 500.
    for bad in (
        {"age_value": 3},
        {"age_unit": "YEARS"},
        {"age_value": 3, "age_unit": "WEEKS"},
        {"age_value": 121, "age_unit": "YEARS"},
        {"age_value": -1, "age_unit": "YEARS"},
    ):
        response = await client.post("/api/v1/patients", json={**base, **bad})
        assert response.status_code == 422, bad

    # Edição troca a idade e devolve a versão nova; sem idade, limpa e mantém o texto legado.
    url = f"/api/v1/patients/{thor['id']}"
    update_base = {
        "name": "Thor",
        "species_id": dog_id,
        "sex": "MALE",
        "owner_name": "Carla Dias",
        "status": "ACTIVE",
    }
    older = await client.patch(
        url,
        json={
            **update_base,
            "age_value": 2,
            "age_unit": "YEARS",
            "expected_row_version": thor["row_version"],
        },
    )
    assert older.status_code == 200
    assert (older.json()["age_value"], older.json()["age_unit"]) == (2, "YEARS")
    assert older.json()["age_description"] == "2 anos"

    cleared = await client.patch(
        url,
        json={
            **update_base,
            "age_description": "adulto",
            "expected_row_version": older.json()["row_version"],
        },
    )
    assert cleared.status_code == 200
    body = cleared.json()
    assert (body["age_value"], body["age_unit"], body["age_recorded_on"]) == (None, None, None)
    assert body["age_description"] == "adulto"

    # A lista devolve os mesmos campos estruturados.
    listed = await client.get("/api/v1/patients", params={"search": "Thor"})
    assert listed.status_code == 200
    assert "age_value" in listed.json()["items"][0]


async def test_patient_free_text_is_trimmed_and_bounded(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """QA 2026-11-19: whitespace-only and 5000-char names used to be stored as sent."""
    dog_id = _get_species_id(session_factory, name="Canino")
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    body = {
        "clinic_id": _clinic_id(session_factory),
        "name": "Rex",
        "species_id": dog_id,
        "sex": "MALE",
        "owner_name": "Maria",
    }

    for field, value in (
        ("name", "   "),
        ("name", "x" * 201),
        ("owner_name", "   "),
        ("owner_name", "x" * 201),
        ("breed", "x" * 101),
        ("owner_phone", "9" * 31),
        ("notes", "x" * 2001),
    ):
        rejected = await client.post("/api/v1/patients", json={**body, field: value})
        assert rejected.status_code == 422, (field, len(value))

    trimmed = await client.post("/api/v1/patients", json={**body, "name": "  Rex  "})
    assert trimmed.status_code == 201
    assert trimmed.json()["name"] == "Rex"

    update = {
        "name": "Rex",
        "species_id": dog_id,
        "sex": "MALE",
        "owner_name": "Maria",
        "status": "ACTIVE",
        "expected_row_version": trimmed.json()["row_version"],
    }
    url = f"/api/v1/patients/{trimmed.json()['id']}"
    for field, value in (("name", "   "), ("owner_name", "x" * 201), ("notes", "x" * 2001)):
        rejected_update = await client.patch(url, json={**update, field: value})
        assert rejected_update.status_code == 422, field
