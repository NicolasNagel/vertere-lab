"""Integração com PostgreSQL real (Testcontainers) — stage de planilha
`.xlsx`, autorização e idempotência de re-stage, ponta a ponta via
HTTPX/ASGI.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN, ROLE_TECHNICAL
from app.shared.infrastructure.database import build_engine, build_session_factory
from tests.imports.pdf_builder import PdfTextItem, build_price_table_pdf
from tests.imports.xlsx_builder import build_workbook, build_xlsx

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="module")
def monkeypatch_module() -> Iterator[pytest.MonkeyPatch]:
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module", autouse=True)
def _migrated_schema(postgres_url: str, monkeypatch_module: pytest.MonkeyPatch) -> None:
    monkeypatch_module.setenv("DATABASE_URL", postgres_url)
    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "backend" / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture
def session_factory(postgres_url: str) -> Iterator[sessionmaker[Session]]:
    engine = build_engine(postgres_url)
    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM import_exceptions"))
        session.execute(text("DELETE FROM import_staging_rows"))
        session.execute(text("DELETE FROM import_batches"))
        session.execute(text("DELETE FROM veterinarian_clinics"))
        session.execute(text("DELETE FROM veterinarians"))
        session.execute(text("DELETE FROM clinics"))
        session.execute(text("DELETE FROM exam_species"))
        session.execute(text("DELETE FROM exams"))
        session.execute(text("DELETE FROM exam_categories"))
        session.execute(text("DELETE FROM patients"))
        session.execute(text("DELETE FROM audit_log"))
        session.execute(text("DELETE FROM users"))
        session.commit()


@pytest.fixture
def settings(postgres_url: str) -> Settings:
    return Settings(
        env="test",
        log_level="WARNING",
        database_url=SecretStr(postgres_url),
        session_cookie_secure=False,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test") as async_client,
        app.router.lifespan_context(app),
    ):
        yield async_client


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


def _spreadsheet_bytes() -> bytes:
    return build_xlsx(
        "Cadastro Clínicas",
        [["Clínica", "Status"], ["Bicho Urbano", "Ativo"], ["Schweitzer", "Ativo"]],
    )


async def test_stage_without_permission_is_forbidden(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory,
        email="technical@vertere.local",
        password="s3nhaForte!",
        role_id=ROLE_TECHNICAL,
    )
    await _login(client, email="technical@vertere.local", password="s3nhaForte!")

    response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", _spreadsheet_bytes(), "application/octet-stream")},
    )

    assert response.status_code == 403


async def test_lab_admin_can_stage_spreadsheet(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", _spreadsheet_bytes(), "application/octet-stream")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["already_staged"] is False
    assert body["sheet_row_counts"] == {"Cadastro Clínicas": 3}
    assert body["batch"]["status"] == "STAGED"


async def test_staging_same_file_twice_is_idempotent(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    content = _spreadsheet_bytes()

    first = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", content, "application/octet-stream")},
    )
    second = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", content, "application/octet-stream")},
    )

    assert first.json()["already_staged"] is False
    assert second.json()["already_staged"] is True
    assert second.json()["batch"]["id"] == first.json()["batch"]["id"]

    with session_factory() as session:
        row_count = session.execute(text("SELECT COUNT(*) FROM import_staging_rows")).scalar_one()
    assert row_count == 3


async def test_stage_rejects_non_xlsx_extension(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.csv", b"a,b\n1,2", "text/csv")},
    )

    assert response.status_code == 422


def _full_pipeline_workbook() -> bytes:
    return build_workbook(
        {
            "Cadastro Clínicas": [
                ["CADASTRO DE CLÍNICAS"],
                ["Clínica", "CNPJ", "Endereço", "Telefone", "E-mail", "Status", "Observação"],
                [
                    "Bea Pet Center",
                    "18.488.074/0001-84",
                    "R. Feliciano Bortolini, 1216",
                    "(47) 9 9914-6833",
                    "beapetcenter@gmail.com",
                    "Ativo",
                    None,
                ],
                [
                    "Reale",
                    "15.033.071/0001-68",
                    "R. Marina Frutuoso, 856",
                    None,
                    None,
                    "Ativo",
                    None,
                ],
                ["Autonomos", None, "Atendimento à Domicilio", None, None, "Ativo", None],
            ],
            "Cadastro Veterinários": [
                ["CADASTRO DE VETERINÁRIOS"],
                ["Clínica", "Nome", "CRMV", "Telefone", "E-mail", "Status", "Observação"],
                ["Autonomos", "Larissa Tomelin", "9142", None, None, "Ativo", None],
            ],
            "Dados": [
                ["REGISTRO DE ATENDIMENTOS"],
                ["Período:"],
                ["Clínica:"],
                [
                    "Clínica",
                    "Data",
                    "Hora",
                    "Ano",
                    "Nº",
                    "Protocolo",
                    "Método de Coleta",
                    "Veterinário",
                ],
                # Case-typo clinic name, matching the real spreadsheet's
                # "Bea pet Center" — must resolve to "Bea Pet Center" and
                # imply a new veterinarian_clinics link for Larissa Tomelin,
                # who the master sheet only registers under "Autonomos".
                [
                    "Bea pet Center",
                    "46025",
                    "0.5",
                    "2026",
                    "1",
                    "1/2026",
                    "Motoboy",
                    "Larissa Tomelin",
                ],
                ["Reale", "46025", "0.5", "2026", "2", "2/2026", "Motoboy", "Larissa Tomelin"],
            ],
        }
    )


async def test_full_fase1_pipeline_creates_clinics_veterinarians_and_history_links(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    content = _full_pipeline_workbook()

    stage_response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", content, "application/octet-stream")},
    )
    assert stage_response.status_code == 200
    batch_id = stage_response.json()["batch"]["id"]

    clinics_response = await client.post(f"/api/v1/imports/{batch_id}/clinics")
    assert clinics_response.status_code == 200
    clinics_body = clinics_response.json()
    assert clinics_body["imported_count"] == 3
    assert clinics_body["exceptions"] == []

    vets_response = await client.post(f"/api/v1/imports/{batch_id}/veterinarians")
    assert vets_response.status_code == 200
    vets_body = vets_response.json()
    assert vets_body["imported_count"] == 1
    assert vets_body["exceptions"] == []

    backfill_response = await client.post(
        f"/api/v1/imports/{batch_id}/veterinarian-clinics/backfill"
    )
    assert backfill_response.status_code == 200
    backfill_body = backfill_response.json()
    # Only the "Bea Pet Center" row implies a *new* link (case-typo
    # resolved automatically); "Reale" hits the same (vet, clinic) pair
    # only if it were the same clinic — here it's a second, distinct new
    # link, since neither was in the master sheet for this vet.
    assert backfill_body["links_created_count"] == 2
    assert backfill_body["exceptions"] == []

    with session_factory() as session:
        clinic_names = set(session.execute(text("SELECT name FROM clinics")).scalars().all())
        link_count = session.execute(text("SELECT COUNT(*) FROM veterinarian_clinics")).scalar_one()

    assert clinic_names == {"Bea Pet Center", "Reale", "Autonomos"}
    # 1 primary link from the master sheet (vet -> Autonomos) + 2 backfilled
    # from history (vet -> Bea Pet Center, vet -> Reale).
    assert link_count == 3


def _exam_catalog_workbook() -> bytes:
    return build_workbook(
        {
            # Real file has no title row on this hidden sheet — row 1 is
            # blank, header lands on row 2, data starts row 3.
            "Suporte": [
                [],
                ["Tipo Exame", "Espécie", "Sexo", "Metodo de Coleta", "Tipo de Atendimento"],
                ["Hematológicos", "Canino", "Macho", "Motoboy", "Normal"],
                ["Perfis", "Felino", "Fêmea", "Internos", "Plantão"],
            ],
            "Dados": [
                ["REGISTRO DE ATENDIMENTOS"],
                ["Período:"],
                ["Clínica:"],
                [
                    "Clínica",
                    "Data",
                    "Hora",
                    "Ano",
                    "Nº",
                    "Protocolo",
                    "Método de Coleta",
                    "Veterinário",
                    "Paciente",
                    "Espécie",
                    "Raça",
                    "Sexo",
                    "Idade",
                    "Proprietário",
                    "Tipo de Exame",
                    "Exame",
                    "Tipo",
                    "Valor",
                ],
                (
                    ["Cantinho Pet", "46025", "0.4"]
                    + [None] * 11
                    + ["Hematológicos", "Hemograma", "Normal", "25"]
                ),
                (
                    ["Schweitzer", "46100", "0.5"]
                    + [None] * 11
                    + ["Perfis", "Check-up 2 + Urinálise", "Normal", "145"]
                ),
            ],
        }
    )


async def test_exam_catalog_pipeline_creates_categories_and_standalone_exams(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    content = _exam_catalog_workbook()

    stage_response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", content, "application/octet-stream")},
    )
    assert stage_response.status_code == 200
    batch_id = stage_response.json()["batch"]["id"]

    categories_response = await client.post(f"/api/v1/imports/{batch_id}/exam-categories")
    assert categories_response.status_code == 200
    categories_body = categories_response.json()
    assert categories_body["imported_count"] == 2

    exams_response = await client.post(f"/api/v1/imports/{batch_id}/exams")
    assert exams_response.status_code == 200
    exams_body = exams_response.json()
    # Only "Hemograma" is standalone; "Check-up 2 + Urinálise" is a combined
    # line and never becomes a catalog candidate from this sheet.
    assert exams_body["imported_count"] == 1
    assert exams_body["exceptions"] == []

    with session_factory() as session:
        category_names = set(
            session.execute(text("SELECT name FROM exam_categories")).scalars().all()
        )
        exam_rows = session.execute(text("SELECT name, price_base FROM exams")).all()

    assert category_names == {"Hematológicos", "Perfis"}
    assert len(exam_rows) == 1
    assert exam_rows[0][0] == "Hemograma"
    assert exam_rows[0][1] == 25


async def test_concurrent_clinic_imports_do_not_duplicate(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    """Regression found via QA against a running instance: two concurrent
    calls to `/imports/{batch_id}/clinics` for the same batch each read
    "not created yet" before either committed, then both inserted it —
    `clinics.name` has no unique constraint (by design: two real clinics
    could share a name). The fix is a per-batch advisory lock
    (`acquire_batch_lock`), not a uniqueness constraint that would impose a
    business rule the domain doesn't actually have."""
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    rows: list[list[str | None]] = [
        ["CADASTRO DE CLÍNICAS"],
        ["Clínica", "CNPJ", "Endereço", "Telefone", "E-mail", "Status", "Observação"],
    ]
    for i in range(20):
        rows.append([f"Clínica Concorrente {i}", None, None, None, None, "Ativo", None])
    content = build_xlsx("Cadastro Clínicas", rows)

    stage_response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", content, "application/octet-stream")},
    )
    batch_id = stage_response.json()["batch"]["id"]

    responses = await asyncio.gather(
        *[client.post(f"/api/v1/imports/{batch_id}/clinics") for _ in range(6)]
    )
    for response in responses:
        assert response.status_code == 200
    total_imported = sum(r.json()["imported_count"] for r in responses)
    assert total_imported == 20  # exactly once each, split across whichever call got there first

    with session_factory() as session:
        row = session.execute(
            text(
                "SELECT COUNT(*), COUNT(DISTINCT name) FROM clinics WHERE name LIKE 'Clínica Concorrente%'"
            )
        ).one()
    assert row[0] == 20
    assert row[1] == 20


def _patients_workbook() -> bytes:
    dados_header: list[str | None] = [
        "Clínica",
        "Data",
        "Hora",
        "Ano",
        "Nº",
        "Protocolo",
        "Método de Coleta",
        "Veterinário",
        "Paciente",
        "Espécie",
        "Raça",
        "Sexo",
        "Idade",
        "Proprietário",
    ]
    return build_workbook(
        {
            "Dados": [
                ["REGISTRO DE ATENDIMENTOS"],
                ["Período:"],
                ["Clínica:"],
                dados_header,
                [
                    "Amizade",
                    "46025",
                    "0.4",
                    "2026",
                    "1",
                    "1/2026",
                    "Motoboy",
                    "Dr. Vet",
                    "Rex",
                    "Canino",
                    "SRD",
                    "Macho",
                    "5a",
                    "Maria (15092)",
                ],
                [
                    "Amizade",
                    "46026",
                    "0.4",
                    "2026",
                    "2",
                    "2/2026",
                    "Motoboy",
                    "Dr. Vet",
                    "Mimosa",
                    "bovino",  # lowercase typo, like the real spreadsheet
                    None,
                    "Fêmea",
                    None,
                    "Priscila (NI)",
                ],
            ]
        }
    )


async def test_patients_pipeline_creates_patients_with_embedded_owner(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    content = _patients_workbook()

    stage_response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", content, "application/octet-stream")},
    )
    assert stage_response.status_code == 200
    batch_id = stage_response.json()["batch"]["id"]

    response = await client.post(f"/api/v1/imports/{batch_id}/patients")
    assert response.status_code == 200
    body = response.json()
    assert body["imported_count"] == 2
    assert body["exceptions"] == []

    with session_factory() as session:
        rows = session.execute(
            text(
                "SELECT p.name, p.owner_name, p.notes, s.name AS species_name "
                "FROM patients p JOIN species s ON s.id = p.species_id "
                "ORDER BY p.name"
            )
        ).all()

    assert [r.name for r in rows] == ["Mimosa", "Rex"]
    mimosa, rex = rows
    assert mimosa.owner_name == "Priscila"
    assert "NI" in mimosa.notes
    assert mimosa.species_name == "Bovino"  # lowercase typo resolved case-insensitively
    assert rex.owner_name == "Maria"
    assert "15092" in rex.notes
    assert rex.species_name == "Canino"


def _full_batch_workbook() -> bytes:
    return build_workbook(
        {
            "Cadastro Clínicas": [
                ["CADASTRO DE CLÍNICAS"],
                ["Clínica", "CNPJ", "Endereço", "Telefone", "E-mail", "Status", "Observação"],
                ["Amizade", None, None, None, None, "Ativo", None],
            ],
            "Cadastro Veterinários": [
                ["CADASTRO DE VETERINÁRIOS"],
                ["Clínica", "Nome", "CRMV", "Telefone", "E-mail", "Status", "Observação"],
                ["Amizade", "Amanda Pozzi", "11816", None, None, "Ativo", None],
            ],
            "Suporte": [[], ["Tipo Exame"], ["Hematológicos"]],
            "Dados": [
                ["REGISTRO DE ATENDIMENTOS"],
                ["Período:"],
                ["Clínica:"],
                [
                    "Clínica",
                    "Data",
                    "Hora",
                    "Ano",
                    "Nº",
                    "Protocolo",
                    "Método de Coleta",
                    "Veterinário",
                    "Paciente",
                    "Espécie",
                    "Raça",
                    "Sexo",
                    "Idade",
                    "Proprietário",
                    "Tipo de Exame",
                    "Exame",
                    "Tipo",
                    "Valor",
                ],
                [
                    "Amizade",
                    "46025",
                    "0.4",
                    "2026",
                    "1",
                    "1/2026",
                    "Motoboy",
                    "Amanda Pozzi",
                    "Rex",
                    "Canino",
                    "SRD",
                    "Macho",
                    "5a",
                    "Maria",
                    "Hematológicos",
                    "Hemograma",
                    "Normal",
                    "25",
                ],
                # Unknown clinic in history -> becomes a backfill-phase exception, never
                # silently created.
                [
                    "Clínica Desconhecida",
                    "46026",
                    "0.4",
                    "2026",
                    "2",
                    "2/2026",
                    "Motoboy",
                    "Amanda Pozzi",
                    "Bidu",
                    "Canino",
                    "SRD",
                    "Macho",
                    "3a",
                    "João",
                    "Hematológicos",
                    "Hemograma",
                    "Normal",
                    "25",
                ],
            ],
        }
    )


async def test_dry_run_persists_nothing(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    content = _full_batch_workbook()

    stage_response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", content, "application/octet-stream")},
    )
    batch_id = stage_response.json()["batch"]["id"]

    response = await client.post(f"/api/v1/imports/{batch_id}/dry-run")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRY_RUN_DONE"
    phase_names = [p["phase"] for p in body["phases"]]
    assert phase_names == [
        "clinics",
        "veterinarians",
        "veterinarian_clinics_backfill",
        "exam_categories",
        "exams",
        "patients",
    ]
    assert body["total_imported_count"] > 0
    assert body["total_exceptions_count"] >= 1  # the unknown-clinic row

    with session_factory() as session:
        counts = session.execute(
            text(
                "SELECT "
                "(SELECT COUNT(*) FROM clinics) AS clinics, "
                "(SELECT COUNT(*) FROM veterinarians) AS veterinarians, "
                "(SELECT COUNT(*) FROM exam_categories) AS exam_categories, "
                "(SELECT COUNT(*) FROM exams) AS exams, "
                "(SELECT COUNT(*) FROM patients) AS patients, "
                "(SELECT COUNT(*) FROM import_exceptions) AS exceptions"
            )
        ).one()

    # Dry-run must leave no trace: every table stays at zero despite the pipeline having
    # genuinely run (the response above proves it computed real counts and exceptions).
    assert counts.clinics == 0
    assert counts.veterinarians == 0
    assert counts.exam_categories == 0
    assert counts.exams == 0
    assert counts.patients == 0
    assert counts.exceptions == 0

    # Re-fetch the batch itself: STAGED, not DRY_RUN_DONE, for the same reason.
    with session_factory() as session:
        status = session.execute(
            text("SELECT status FROM import_batches WHERE id = :id"), {"id": batch_id}
        ).scalar_one()
    assert status == "STAGED"


async def test_commit_persists_data_and_exceptions_and_lists_them(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")
    content = _full_batch_workbook()

    stage_response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", content, "application/octet-stream")},
    )
    batch_id = stage_response.json()["batch"]["id"]

    commit_response = await client.post(f"/api/v1/imports/{batch_id}/commit")
    assert commit_response.status_code == 200
    body = commit_response.json()
    assert body["status"] == "COMMITTED"
    assert body["total_imported_count"] > 0
    assert body["total_exceptions_count"] >= 1

    with session_factory() as session:
        counts = session.execute(
            text(
                "SELECT "
                "(SELECT COUNT(*) FROM clinics) AS clinics, "
                "(SELECT COUNT(*) FROM veterinarians) AS veterinarians, "
                "(SELECT COUNT(*) FROM patients) AS patients"
            )
        ).one()
        status = session.execute(
            text("SELECT status FROM import_batches WHERE id = :id"), {"id": batch_id}
        ).scalar_one()
    assert counts.clinics == 1
    assert counts.veterinarians == 1
    # 2, not 1: `Patient` has no clinic reference (by design — see
    # `import_patients.py`), so the row under "Clínica Desconhecida" still
    # legitimately creates its own patient; only the clinics/backfill phases
    # reject that clinic name.
    assert counts.patients == 2
    assert status == "COMMITTED"

    exceptions_response = await client.get(f"/api/v1/imports/{batch_id}/exceptions")
    assert exceptions_response.status_code == 200
    exceptions_body = exceptions_response.json()
    assert exceptions_body["batch_id"] == batch_id
    assert len(exceptions_body["exceptions"]) == body["total_exceptions_count"]
    assert any(
        "Clínica Desconhecida" in e["message"]
        or "Bidu" in e["message"]
        or e["phase"] == "veterinarian_clinics_backfill"
        for e in exceptions_body["exceptions"]
    )

    # Re-running commit on the same batch must not duplicate anything.
    second_commit = await client.post(f"/api/v1/imports/{batch_id}/commit")
    assert second_commit.status_code == 200
    assert second_commit.json()["total_imported_count"] == 0

    with session_factory() as session:
        clinics_count = session.execute(text("SELECT COUNT(*) FROM clinics")).scalar_one()
    assert clinics_count == 1


def _price_table_pdf(*, exam_name: str, price: str, unknown_name: str) -> bytes:
    return build_price_table_pdf(
        [
            PdfTextItem(text="Exames", x=30, y=750, size=20),
            PdfTextItem(text=exam_name, x=50, y=700, size=12),
            PdfTextItem(text=f"R$ {price}", x=480, y=700, size=8),
            PdfTextItem(text=unknown_name, x=50, y=680, size=12),
            PdfTextItem(text="R$ 99,00", x=480, y=680, size=8),
        ]
    )


async def test_dry_run_price_table_persists_nothing(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    # Seed a real catalog exam ("Hemograma", R$ 25,00) via the existing xlsx pipeline, same
    # real Postgres — Fase 2b only ever updates an exam that already exists.
    xlsx_stage = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", _exam_catalog_workbook(), "application/octet-stream")},
    )
    xlsx_batch_id = xlsx_stage.json()["batch"]["id"]
    await client.post(f"/api/v1/imports/{xlsx_batch_id}/exam-categories")
    await client.post(f"/api/v1/imports/{xlsx_batch_id}/exams")

    pdf = _price_table_pdf(
        exam_name="Hemograma", price="30,00", unknown_name="Exame Fora Do Catalogo"
    )
    pdf_stage = await client.post(
        "/api/v1/imports/price-table/stage",
        files={"file": ("tabela.pdf", pdf, "application/pdf")},
    )
    assert pdf_stage.status_code == 200
    pdf_body = pdf_stage.json()
    assert pdf_body["already_staged"] is False
    assert pdf_body["item_count"] == 2
    pdf_batch_id = pdf_body["batch"]["id"]

    dry_run = await client.post(f"/api/v1/imports/{pdf_batch_id}/price-table/dry-run")
    assert dry_run.status_code == 200
    dry_run_body = dry_run.json()
    assert dry_run_body["imported_count"] == 1
    assert len(dry_run_body["exceptions"]) == 1

    with session_factory() as session:
        price = session.execute(
            text("SELECT price_base FROM exams WHERE name = 'Hemograma'")
        ).scalar_one()
        exceptions_count = session.execute(
            text("SELECT COUNT(*) FROM import_exceptions")
        ).scalar_one()
        pdf_batch_status = session.execute(
            text("SELECT status FROM import_batches WHERE id = :id"), {"id": pdf_batch_id}
        ).scalar_one()

    # Dry-run computed a real price difference above but must not have written it.
    assert price == 25
    assert exceptions_count == 0
    assert pdf_batch_status == "STAGED"


async def test_commit_price_table_updates_price_and_reports_unmatched_exam(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _create_user(
        session_factory, email="admin@vertere.local", password="s3nhaForte!", role_id=ROLE_LAB_ADMIN
    )
    await _login(client, email="admin@vertere.local", password="s3nhaForte!")

    xlsx_stage = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", _exam_catalog_workbook(), "application/octet-stream")},
    )
    xlsx_batch_id = xlsx_stage.json()["batch"]["id"]
    await client.post(f"/api/v1/imports/{xlsx_batch_id}/exam-categories")
    await client.post(f"/api/v1/imports/{xlsx_batch_id}/exams")

    pdf = _price_table_pdf(
        exam_name="Hemograma", price="30,00", unknown_name="Exame Fora Do Catalogo"
    )
    pdf_stage = await client.post(
        "/api/v1/imports/price-table/stage",
        files={"file": ("tabela.pdf", pdf, "application/pdf")},
    )
    pdf_batch_id = pdf_stage.json()["batch"]["id"]

    commit = await client.post(f"/api/v1/imports/{pdf_batch_id}/price-table/commit")
    assert commit.status_code == 200
    commit_body = commit.json()
    assert commit_body["status"] == "COMMITTED"
    assert commit_body["imported_count"] == 1
    assert len(commit_body["exceptions"]) == 1
    assert "Exame Fora Do Catalogo" in commit_body["exceptions"][0]["message"]

    with session_factory() as session:
        price = session.execute(
            text("SELECT price_base FROM exams WHERE name = 'Hemograma'")
        ).scalar_one()
        audit_action = session.execute(
            text(
                "SELECT action FROM audit_log WHERE entity_type = 'exam' "
                "AND action = 'exams.price_updated_from_price_table'"
            )
        ).scalar_one()

    assert price == 30
    assert audit_action == "exams.price_updated_from_price_table"

    exceptions_response = await client.get(f"/api/v1/imports/{pdf_batch_id}/exceptions")
    assert exceptions_response.status_code == 200
    assert len(exceptions_response.json()["exceptions"]) == 1

    # Re-committing must not duplicate the exception or re-audit the (now unchanged) price.
    second_commit = await client.post(f"/api/v1/imports/{pdf_batch_id}/price-table/commit")
    assert second_commit.status_code == 200
    assert second_commit.json()["imported_count"] == 0

    with session_factory() as session:
        exceptions_count = session.execute(
            text("SELECT COUNT(*) FROM import_exceptions WHERE batch_id = :id"),
            {"id": pdf_batch_id},
        ).scalar_one()
        audit_count = session.execute(
            text(
                "SELECT COUNT(*) FROM audit_log WHERE entity_type = 'exam' "
                "AND action = 'exams.price_updated_from_price_table'"
            )
        ).scalar_one()

    assert exceptions_count == 1
    assert audit_count == 1
