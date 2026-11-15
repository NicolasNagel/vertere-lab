"""Integração com PostgreSQL real (Testcontainers) — CRUD de categorias de
exame e de exames (com preço e espécies), ponta a ponta via HTTPX/ASGI.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_FINANCE, ROLE_LAB_ADMIN, ROLE_TECHNICAL

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM audit_log"))
        session.execute(text("DELETE FROM exam_panel_items"))
        session.execute(text("DELETE FROM exam_species"))
        session.execute(text("DELETE FROM exams"))
        session.execute(text("DELETE FROM exam_categories"))
        session.execute(text("DELETE FROM users"))
        session.commit()


def _get_species_id(session_factory: sessionmaker[Session], *, name: str) -> str:
    with session_factory() as session:
        row = session.execute(
            text("SELECT id FROM species WHERE name = :name"), {"name": name}
        ).one()
        return str(row[0])


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


async def _create_category(client: httpx.AsyncClient, *, name: str = "Hematologia") -> str:
    response = await client.post("/api/v1/exam-categories", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["id"])


async def _login_as(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, email: str, role_id: UUID
) -> None:
    _create_user(session_factory, email=email, password="s3nhaForte!", role_id=role_id)
    await _login(client, email=email, password="s3nhaForte!")


async def test_exam_categories_are_permission_gated_unique_versioned_and_deactivated_not_deleted(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(
        client, session_factory, email="technical@vertere.local", role_id=ROLE_TECHNICAL
    )
    forbidden = await client.post("/api/v1/exam-categories", json={"name": "Hematologia"})
    assert forbidden.status_code == 403

    await _login_as(client, session_factory, email="finance@vertere.local", role_id=ROLE_FINANCE)
    finance = await client.post("/api/v1/exam-categories", json={"name": "Financeira"})
    assert finance.status_code == 201

    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    created = await client.post("/api/v1/exam-categories", json={"name": "Hematologia"})
    assert created.status_code == 201
    category = created.json()
    assert (category["name"], category["status"]) == ("Hematologia", "ACTIVE")
    fetched = await client.get(f"/api/v1/exam-categories/{category['id']}")
    assert (fetched.status_code, fetched.json()["name"]) == (200, "Hematologia")

    # Nome duplicado (sem distinguir caixa) conflita.
    duplicate = await client.post("/api/v1/exam-categories", json={"name": "hematologia"})
    assert duplicate.status_code == 409

    # Versão errada conflita; versões encadeadas usam a devolvida pela edição anterior.
    url = f"/api/v1/exam-categories/{category['id']}"
    stale = await client.patch(
        url,
        json={
            "name": "Hematologia Atualizada",
            "status": "ACTIVE",
            "expected_row_version": category["row_version"] + 1,
        },
    )
    assert stale.status_code == 409
    first = await client.patch(
        url,
        json={
            "name": "Versao Um",
            "status": "ACTIVE",
            "expected_row_version": category["row_version"],
        },
    )
    assert first.status_code == 200
    assert first.json()["row_version"] == category["row_version"] + 1
    second = await client.patch(
        url,
        json={
            "name": "Versao Dois",
            "status": "ACTIVE",
            "expected_row_version": first.json()["row_version"],
        },
    )
    assert second.status_code == 200
    assert second.json()["row_version"] == category["row_version"] + 2

    # Desativar preserva o registro e a lista de ativas deixa de incluí-lo.
    retired = await client.post("/api/v1/exam-categories", json={"name": "Descontinuada"})
    deactivated = await client.post(f"/api/v1/exam-categories/{retired.json()['id']}/deactivate")
    assert deactivated.status_code == 200
    assert (deactivated.json()["status"], deactivated.json()["name"]) == (
        "INACTIVE",
        "Descontinuada",
    )
    active = await client.get("/api/v1/exam-categories/active")
    assert active.status_code == 200
    assert sorted(item["name"] for item in active.json()["items"]) == ["Financeira", "Versao Dois"]


async def test_exams_get_distinct_codes_are_versioned_filterable_and_hide_price_without_permission(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    dog_id = _get_species_id(session_factory, name="Canino")
    cat_id = _get_species_id(session_factory, name="Felino")
    category_id = await _create_category(client)

    def payload(name: str, price: str, species_id: str) -> dict[str, object]:
        return {
            "name": name,
            "category_id": category_id,
            "price_base": price,
            "species_ids": [species_id],
        }

    created = await client.post(
        "/api/v1/exams", json=payload("Hemograma completo", "85.00", dog_id)
    )
    assert created.status_code == 201
    exam = created.json()
    assert len(exam["code"]) == 8
    assert exam["code"].isalnum()
    assert exam["code"] == exam["code"].upper()
    assert Decimal(exam["price_base"]) == Decimal("85.00")
    fetched = await client.get(f"/api/v1/exams/{exam['id']}")
    assert (fetched.status_code, Decimal(fetched.json()["price_base"])) == (200, Decimal("85.00"))

    other = await client.post("/api/v1/exams", json=payload("Hemograma felino", "90.00", cat_id))
    assert other.status_code == 201
    assert other.json()["code"] != exam["code"]  # códigos gerados são distintos

    by_species = await client.get("/api/v1/exams", params={"species_id": cat_id})
    assert by_species.status_code == 200
    assert by_species.json()["total"] == 1
    assert by_species.json()["items"][0]["name"] == "Hemograma felino"

    # Edições encadeadas usam a versão devolvida pela anterior.
    url = f"/api/v1/exams/{exam['id']}"
    versions = [exam["row_version"]]
    for name in ("Hemograma revisado", "Hemograma revisado novamente"):
        update = await client.patch(
            url,
            json={
                **payload(name, "85.00", dog_id),
                "status": "ACTIVE",
                "expected_row_version": versions[-1],
            },
        )
        assert update.status_code == 200
        versions.append(update.json()["row_version"])
    assert versions == [exam["row_version"], exam["row_version"] + 1, exam["row_version"] + 2]

    deactivated = await client.post(f"{url}/deactivate")
    assert deactivated.status_code == 200
    assert (deactivated.json()["status"], deactivated.json()["name"]) == (
        "INACTIVE",
        "Hemograma revisado novamente",
    )

    # Sem permissão de preço o valor some da leitura e criar exame é negado.
    await _login_as(
        client, session_factory, email="technical@vertere.local", role_id=ROLE_TECHNICAL
    )
    hidden = await client.get(url)
    assert (hidden.status_code, hidden.json()["price_base"]) == (200, None)
    denied = await client.post("/api/v1/exams", json=payload("Hemograma completo", "85.00", dog_id))
    assert denied.status_code == 403


async def test_import_exams_is_permission_gated_csv_only_and_reports_row_errors(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    header = "code,name,category,price_base,species\n"
    await _login_as(
        client, session_factory, email="technical@vertere.local", role_id=ROLE_TECHNICAL
    )
    forbidden = await client.post(
        "/api/v1/exams/import",
        files={
            "file": (
                "exams.csv",
                header + "HEM001,Hemograma,Hematologia,85.00,Canino\n",
                "text/csv",
            )
        },
    )
    assert forbidden.status_code == 403

    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    await _create_category(client, name="Hematologia")
    not_csv = await client.post(
        "/api/v1/exams/import", files={"file": ("exams.txt", "code,name\n", "text/plain")}
    )
    assert not_csv.status_code == 422

    csv_content = (
        header
        + "HEM001,Hemograma completo,Hematologia,85.00,Canino\n"
        + "HEM002,Bioquímico,Categoria Inexistente,120.00,Felino\n"
    )
    response = await client.post(
        "/api/v1/exams/import", files={"file": ("exams.csv", csv_content, "text/csv")}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["line"] == 3
    assert "Categoria Inexistente" in body["errors"][0]["message"]

    listed = await client.get("/api/v1/exams", params={"search": "HEM001"})
    assert listed.json()["total"] == 1


async def test_exam_panels_compose_validate_snapshot_and_block_unsafe_changes(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    dog_id = _get_species_id(session_factory, name="Canino")
    category_id = await _create_category(client)

    async def create(name: str, price: str, **extra: object) -> dict[str, object]:
        response = await client.post(
            "/api/v1/exams",
            json={
                "name": name,
                "category_id": category_id,
                "price_base": price,
                "species_ids": [dog_id],
                **extra,
            },
        )
        assert response.status_code == 201, response.text
        return dict(response.json())

    hemograma = await create("Hemograma", "40.00")
    alt = await create("ALT", "20.00")
    ureia = await create("Ureia", "20.00")
    assert (hemograma["is_panel"], hemograma["component_exam_ids"]) == (False, [])

    # Pacote tem preço próprio (não é a soma dos componentes) e guarda a ordem escolhida.
    panel = await create(
        "CHECK-UP 1", "70.00", component_exam_ids=[alt["id"], hemograma["id"], ureia["id"]]
    )
    assert panel["is_panel"] is True
    assert panel["component_exam_ids"] == [alt["id"], hemograma["id"], ureia["id"]]
    assert Decimal(str(panel["price_base"])) == Decimal("70.00")
    refetched = await client.get(f"/api/v1/exams/{panel['id']}")
    assert refetched.json()["component_exam_ids"] == panel["component_exam_ids"]

    # Regras: sem aninhar pacote, sem repetir, sem componente inexistente ou inativo.
    nested = await client.post(
        "/api/v1/exams",
        json={
            "name": "Pacote de pacote",
            "category_id": category_id,
            "price_base": "10.00",
            "species_ids": [dog_id],
            "component_exam_ids": [panel["id"]],
        },
    )
    assert nested.status_code == 422
    repeated = await client.post(
        "/api/v1/exams",
        json={
            "name": "Repetido",
            "category_id": category_id,
            "price_base": "10.00",
            "species_ids": [dog_id],
            "component_exam_ids": [alt["id"], alt["id"]],
        },
    )
    assert repeated.status_code == 422
    missing = await client.post(
        "/api/v1/exams",
        json={
            "name": "Fantasma",
            "category_id": category_id,
            "price_base": "10.00",
            "species_ids": [dog_id],
            "component_exam_ids": [str(uuid4())],
        },
    )
    assert missing.status_code == 422

    # Componente de pacote ativo não pode ser inativado (nem por PATCH nem por deactivate).
    blocked = await client.post(f"/api/v1/exams/{alt['id']}/deactivate")
    assert blocked.status_code == 409
    assert "CHECK-UP 1" in blocked.json()["error"]["message"]
    blocked_patch = await client.patch(
        f"/api/v1/exams/{alt['id']}",
        json={
            "name": "ALT",
            "category_id": category_id,
            "price_base": "20.00",
            "species_ids": [dog_id],
            "status": "INACTIVE",
            "expected_row_version": alt["row_version"],
            "reason": "Teste de bloqueio",
        },
    )
    assert blocked_patch.status_code == 409

    # Exame simples não vira pacote, nem o contrário.
    to_panel = await client.patch(
        f"/api/v1/exams/{ureia['id']}",
        json={
            "name": "Ureia",
            "category_id": category_id,
            "price_base": "20.00",
            "species_ids": [dog_id],
            "component_exam_ids": [alt["id"]],
            "status": "ACTIVE",
            "expected_row_version": ureia["row_version"],
        },
    )
    assert to_panel.status_code == 422
    to_plain = await client.patch(
        f"/api/v1/exams/{panel['id']}",
        json={
            "name": "CHECK-UP 1",
            "category_id": category_id,
            "price_base": "70.00",
            "species_ids": [dog_id],
            "component_exam_ids": [],
            "status": "ACTIVE",
            "expected_row_version": panel["row_version"],
        },
    )
    assert to_plain.status_code == 422

    # Editar a composição funciona e muda a versão; pacote inativado libera o componente.
    edited = await client.patch(
        f"/api/v1/exams/{panel['id']}",
        json={
            "name": "CHECK-UP 1",
            "category_id": category_id,
            "price_base": "70.00",
            "species_ids": [dog_id],
            "component_exam_ids": [hemograma["id"], alt["id"]],
            "status": "ACTIVE",
            "expected_row_version": panel["row_version"],
        },
    )
    assert edited.status_code == 200
    assert edited.json()["component_exam_ids"] == [hemograma["id"], alt["id"]]
    assert (await client.post(f"/api/v1/exams/{panel['id']}/deactivate")).status_code == 200
    assert (await client.post(f"/api/v1/exams/{alt['id']}/deactivate")).status_code == 200
