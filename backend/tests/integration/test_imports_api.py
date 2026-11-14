"""Integração com PostgreSQL real (Testcontainers) — stage de planilha
`.xlsx`, autorização e idempotência de re-stage, ponta a ponta via
HTTPX/ASGI.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.modules.identity.infrastructure.models import LabMembershipModel, UserModel
from app.modules.identity.infrastructure.seed import ROLE_LAB_ADMIN, ROLE_TECHNICAL
from tests.imports.pdf_builder import PdfTextItem, build_price_table_pdf
from tests.imports.xlsx_builder import build_workbook, build_xlsx

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _reset_data(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        session.execute(text("DELETE FROM import_exceptions"))
        session.execute(text("DELETE FROM attendance_exams"))
        session.execute(text("DELETE FROM attendances"))
        session.execute(text("DELETE FROM attendance_sequences"))
        session.execute(text("DELETE FROM import_staging_rows"))
        session.execute(text("DELETE FROM import_batches"))
        session.execute(text("DELETE FROM veterinarian_clinics"))
        session.execute(text("DELETE FROM veterinarians"))
        session.execute(text("DELETE FROM clinics"))
        session.execute(text("DELETE FROM exam_panel_items"))
        session.execute(text("DELETE FROM exam_species"))
        session.execute(text("DELETE FROM exams"))
        session.execute(text("DELETE FROM exam_categories"))
        session.execute(text("DELETE FROM patients"))
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


def _spreadsheet_bytes() -> bytes:
    return build_xlsx(
        "Cadastro Clínicas",
        [["Clínica", "Status"], ["Bicho Urbano", "Ativo"], ["Schweitzer", "Ativo"]],
    )


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


def _attendance_history_workbook() -> bytes:
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
        "Tipo de Exame",
        "Exame",
        "Tipo",
        "Valor",
        "Desconto",
        "Adicional",
        "Valor Total",
    ]
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
            "Suporte": [[], ["Tipo Exame"], ["Hematológicos"], ["Perfis"], ["Urinários"]],
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
                    "75.00",
                    None,
                    None,
                    "75.00",
                ],
                # Standalone occurrences so Fase 2/3 (exams-from-history)
                # actually creates "Check-up 2" (120) and "Urinálise" (60)
                # in the catalog — the combined line below can only resolve
                # its components against exams that already exist.
                [
                    "Amizade",
                    "46025",
                    "0.41",
                    "2026",
                    "2",
                    "2/2026",
                    "Motoboy",
                    "Amanda Pozzi",
                    "Rex",
                    "Canino",
                    "SRD",
                    "Macho",
                    "5a",
                    "Maria",
                    "Perfis",
                    "Check-up 2",
                    "Normal",
                    "120.00",
                    None,
                    None,
                    "120.00",
                ],
                [
                    "Amizade",
                    "46025",
                    "0.42",
                    "2026",
                    "3",
                    "3/2026",
                    "Motoboy",
                    "Amanda Pozzi",
                    "Rex",
                    "Canino",
                    "SRD",
                    "Macho",
                    "5a",
                    "Maria",
                    "Urinários",
                    "Urinálise",
                    "Normal",
                    "60.00",
                    None,
                    None,
                    "60.00",
                ],
                # Combined line — split proportionally by catalog weight
                # (Check-up 2: 120 / Urinálise: 60 -> 2:1) over the real
                # recorded total of 135 (a 45 discount was applied).
                [
                    "Amizade",
                    "46025",
                    "0.45",
                    "2026",
                    "4",
                    "4/2026",
                    "Motoboy",
                    "Amanda Pozzi",
                    "Rex",
                    "Canino",
                    "SRD",
                    "Macho",
                    "5a",
                    "Maria",
                    "Perfis",
                    "Check-up 2 + Urinálise",
                    "Normal",
                    "180.00",
                    "45.00",
                    None,
                    "135.00",
                ],
                # The known "linha TOTAIS" residual case — no clinic, a
                # value with nothing behind it, must never become an
                # AttendanceRecord.
                [None] * 20 + ["100.00"],
            ],
        }
    )


async def _run_full_cadastro_pipeline(client: httpx.AsyncClient) -> str:
    stage_response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={
            "file": ("planilha.xlsx", _attendance_history_workbook(), "application/octet-stream")
        },
    )
    batch_id: str = stage_response.json()["batch"]["id"]
    for phase in ("clinics", "veterinarians", "veterinarian-clinics/backfill"):
        response = await client.post(f"/api/v1/imports/{batch_id}/{phase}")
        assert response.status_code == 200
    for phase in ("exam-categories", "exams", "patients"):
        response = await client.post(f"/api/v1/imports/{batch_id}/{phase}")
        assert response.status_code == 200
    return batch_id


async def _login_as(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session], *, email: str, role_id: UUID
) -> None:
    _create_user(session_factory, email=email, password="s3nhaForte!", role_id=role_id)
    await _login(client, email=email, password="s3nhaForte!")


async def _stage(client: httpx.AsyncClient, content: bytes) -> str:
    response = await client.post(
        "/api/v1/imports/spreadsheet/stage",
        files={"file": ("planilha.xlsx", content, "application/octet-stream")},
    )
    assert response.status_code == 200
    batch_id: str = response.json()["batch"]["id"]
    return batch_id


async def test_spreadsheet_stage_is_permission_gated_idempotent_and_rejects_bad_uploads(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    stage_url = "/api/v1/imports/spreadsheet/stage"
    content = _spreadsheet_bytes()
    await _login_as(
        client, session_factory, email="technical@vertere.local", role_id=ROLE_TECHNICAL
    )
    forbidden = await client.post(
        stage_url, files={"file": ("planilha.xlsx", content, "application/octet-stream")}
    )
    assert forbidden.status_code == 403

    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    first = await client.post(
        stage_url, files={"file": ("planilha.xlsx", content, "application/octet-stream")}
    )
    assert first.status_code == 200
    assert first.json()["already_staged"] is False
    assert first.json()["sheet_row_counts"] == {"Cadastro Clínicas": 3}
    assert first.json()["batch"]["status"] == "STAGED"

    # Reenviar o mesmo arquivo devolve o mesmo lote sem duplicar linhas.
    second = await client.post(
        stage_url, files={"file": ("planilha.xlsx", content, "application/octet-stream")}
    )
    assert second.json()["already_staged"] is True
    assert second.json()["batch"]["id"] == first.json()["batch"]["id"]
    with session_factory() as session:
        row_count = session.execute(text("SELECT COUNT(*) FROM import_staging_rows")).scalar_one()
    assert row_count == 3

    # Extensão errada (422) e arquivo grande demais (413) nos dois endpoints.
    oversized = b"x" * (20 * 1024 * 1024 + 1)
    uploads = {
        "xlsx_wrong_extension": (stage_url, ("planilha.csv", b"a,b\n1,2", "text/csv")),
        "pdf_wrong_extension": (
            "/api/v1/imports/price-table/stage",
            ("tabela.txt", b"abc", "text/plain"),
        ),
        "xlsx_oversized": (stage_url, ("planilha.xlsx", oversized, "application/octet-stream")),
        "pdf_oversized": (
            "/api/v1/imports/price-table/stage",
            ("tabela.pdf", oversized, "application/pdf"),
        ),
    }
    statuses = {
        label: (await client.post(url, files={"file": file})).status_code
        for label, (url, file) in uploads.items()
    }
    assert statuses == {
        "xlsx_wrong_extension": 422,
        "pdf_wrong_extension": 422,
        "xlsx_oversized": 413,
        "pdf_oversized": 413,
    }


async def test_cadastro_phases_import_clinics_veterinarians_links_catalog_and_patients(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)

    # Clínicas -> veterinários -> backfill de vínculos vindos do histórico.
    batch_id = await _stage(client, _full_pipeline_workbook())
    clinics = (await client.post(f"/api/v1/imports/{batch_id}/clinics")).json()
    assert (clinics["imported_count"], clinics["exceptions"]) == (3, [])
    vets = (await client.post(f"/api/v1/imports/{batch_id}/veterinarians")).json()
    assert (vets["imported_count"], vets["exceptions"]) == (1, [])
    backfill = await client.post(f"/api/v1/imports/{batch_id}/veterinarian-clinics/backfill")
    assert backfill.status_code == 200
    # "Bea pet Center" (typo de caixa) resolve sozinho e "Reale" é outro vínculo novo.
    assert backfill.json()["links_created_count"] == 2
    assert backfill.json()["exceptions"] == []
    with session_factory() as session:
        clinic_names = set(session.execute(text("SELECT name FROM clinics")).scalars().all())
        link_count = session.execute(text("SELECT COUNT(*) FROM veterinarian_clinics")).scalar_one()
    assert clinic_names == {"Bea Pet Center", "Reale", "Autonomos"}
    # 1 vínculo da planilha mestre (Autonomos) + 2 do histórico.
    assert link_count == 3

    # Regressão: chamadas concorrentes de `/clinics` no mesmo lote não duplicam
    # (`clinics.name` não é único; a garantia é o advisory lock por lote).
    rows: list[list[str | None]] = [
        ["CADASTRO DE CLÍNICAS"],
        ["Clínica", "CNPJ", "Endereço", "Telefone", "E-mail", "Status", "Observação"],
        *[[f"Clínica Concorrente {i}", None, None, None, None, "Ativo", None] for i in range(20)],
    ]
    concurrent_batch = await _stage(client, build_xlsx("Cadastro Clínicas", rows))
    responses = await asyncio.gather(
        *[client.post(f"/api/v1/imports/{concurrent_batch}/clinics") for _ in range(6)]
    )
    assert [response.status_code for response in responses] == [200] * 6
    assert sum(r.json()["imported_count"] for r in responses) == 20
    with session_factory() as session:
        row = session.execute(
            text(
                "SELECT COUNT(*), COUNT(DISTINCT name) FROM clinics "
                "WHERE name LIKE 'Clínica Concorrente%'"
            )
        ).one()
    assert (row[0], row[1]) == (20, 20)

    # Catálogo: categorias e só o exame avulso (a linha combinada não vira candidata).
    catalog_batch = await _stage(client, _exam_catalog_workbook())
    categories = (await client.post(f"/api/v1/imports/{catalog_batch}/exam-categories")).json()
    assert categories["imported_count"] == 2
    exams = (await client.post(f"/api/v1/imports/{catalog_batch}/exams")).json()
    assert (exams["imported_count"], exams["exceptions"]) == (1, [])
    with session_factory() as session:
        category_names = set(
            session.execute(text("SELECT name FROM exam_categories")).scalars().all()
        )
        exam_rows = session.execute(text("SELECT name, price_base FROM exams")).all()
    assert category_names == {"Hematológicos", "Perfis"}
    assert [(row[0], row[1]) for row in exam_rows] == [("Hemograma", 25)]

    # Pacientes com tutor embutido; espécie em minúsculas resolve sem diferenciar caixa.
    patients_batch = await _stage(client, _patients_workbook())
    patients = (await client.post(f"/api/v1/imports/{patients_batch}/patients")).json()
    assert (patients["imported_count"], patients["exceptions"]) == (2, [])
    with session_factory() as session:
        patient_rows = session.execute(
            text(
                "SELECT p.name, p.owner_name, p.notes, s.name AS species_name "
                "FROM patients p JOIN species s ON s.id = p.species_id ORDER BY p.name"
            )
        ).all()
    mimosa, rex = patient_rows
    assert (mimosa.name, mimosa.owner_name, mimosa.species_name) == ("Mimosa", "Priscila", "Bovino")
    assert "NI" in mimosa.notes
    assert (rex.name, rex.owner_name, rex.species_name) == ("Rex", "Maria", "Canino")
    assert "15092" in rex.notes


async def test_batch_dry_run_persists_nothing_then_commit_persists_and_is_idempotent(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    batch_id = await _stage(client, _full_batch_workbook())

    dry_run = await client.post(f"/api/v1/imports/{batch_id}/dry-run")
    assert dry_run.status_code == 200
    dry_body = dry_run.json()
    assert dry_body["status"] == "DRY_RUN_DONE"
    assert [p["phase"] for p in dry_body["phases"]] == [
        "clinics",
        "veterinarians",
        "veterinarian_clinics_backfill",
        "exam_categories",
        "exams",
        "patients",
    ]
    assert dry_body["total_imported_count"] > 0
    assert dry_body["total_exceptions_count"] >= 1  # a linha da clínica desconhecida

    with session_factory() as session:
        counts = session.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM clinics) AS clinics, "
                "(SELECT COUNT(*) FROM veterinarians) AS veterinarians, "
                "(SELECT COUNT(*) FROM exam_categories) AS exam_categories, "
                "(SELECT COUNT(*) FROM exams) AS exams, "
                "(SELECT COUNT(*) FROM patients) AS patients, "
                "(SELECT COUNT(*) FROM import_exceptions) AS exceptions"
            )
        ).one()
        status = session.execute(
            text("SELECT status FROM import_batches WHERE id = :id"), {"id": batch_id}
        ).scalar_one()
    # O dry-run calculou contagens reais, mas não deixa rastro.
    assert tuple(counts) == (0, 0, 0, 0, 0, 0)
    assert status == "STAGED"

    commit = await client.post(f"/api/v1/imports/{batch_id}/commit")
    assert commit.status_code == 200
    body = commit.json()
    assert body["status"] == "COMMITTED"
    assert body["total_imported_count"] > 0
    assert body["total_exceptions_count"] >= 1
    with session_factory() as session:
        counts = session.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM clinics) AS clinics, "
                "(SELECT COUNT(*) FROM veterinarians) AS veterinarians, "
                "(SELECT COUNT(*) FROM patients) AS patients"
            )
        ).one()
        status = session.execute(
            text("SELECT status FROM import_batches WHERE id = :id"), {"id": batch_id}
        ).scalar_one()
    # 2 pacientes: `Patient` não referencia clínica, então a linha da clínica
    # desconhecida ainda cria o próprio paciente; só clínicas/backfill a rejeitam.
    assert (counts.clinics, counts.veterinarians, counts.patients) == (1, 1, 2)
    assert status == "COMMITTED"

    listed = await client.get(f"/api/v1/imports/{batch_id}/exceptions")
    assert listed.status_code == 200
    assert listed.json()["batch_id"] == batch_id
    assert len(listed.json()["exceptions"]) == body["total_exceptions_count"]
    assert any(
        "Clínica Desconhecida" in e["message"]
        or "Bidu" in e["message"]
        or e["phase"] == "veterinarian_clinics_backfill"
        for e in listed.json()["exceptions"]
    )

    # Reexecutar o commit do mesmo lote não duplica nada.
    again = await client.post(f"/api/v1/imports/{batch_id}/commit")
    assert again.status_code == 200
    assert again.json()["total_imported_count"] == 0
    with session_factory() as session:
        assert session.execute(text("SELECT COUNT(*) FROM clinics")).scalar_one() == 1


async def test_price_table_dry_run_persists_nothing_then_commit_updates_price_and_is_idempotent(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)

    # Exame real "Hemograma" (R$ 25,00) pelo pipeline xlsx: a Fase 2b só atualiza o que existe.
    catalog_batch = await _stage(client, _exam_catalog_workbook())
    await client.post(f"/api/v1/imports/{catalog_batch}/exam-categories")
    await client.post(f"/api/v1/imports/{catalog_batch}/exams")

    pdf_stage = await client.post(
        "/api/v1/imports/price-table/stage",
        files={
            "file": (
                "tabela.pdf",
                _price_table_pdf(
                    exam_name="Hemograma", price="30,00", unknown_name="Exame Fora Do Catalogo"
                ),
                "application/pdf",
            )
        },
    )
    assert pdf_stage.status_code == 200
    assert pdf_stage.json()["already_staged"] is False
    assert pdf_stage.json()["item_count"] == 2
    pdf_batch_id = pdf_stage.json()["batch"]["id"]

    def snapshot() -> tuple[object, object, object]:
        with session_factory() as session:
            return (
                session.execute(
                    text("SELECT price_base FROM exams WHERE name = 'Hemograma'")
                ).scalar_one(),
                session.execute(text("SELECT COUNT(*) FROM import_exceptions")).scalar_one(),
                session.execute(
                    text("SELECT status FROM import_batches WHERE id = :id"), {"id": pdf_batch_id}
                ).scalar_one(),
            )

    dry_run = await client.post(f"/api/v1/imports/{pdf_batch_id}/price-table/dry-run")
    assert dry_run.status_code == 200
    assert dry_run.json()["imported_count"] == 1
    assert len(dry_run.json()["exceptions"]) == 1
    # O dry-run calculou a diferença de preço, mas não gravou nada.
    assert snapshot() == (25, 0, "STAGED")

    commit = await client.post(f"/api/v1/imports/{pdf_batch_id}/price-table/commit")
    assert commit.status_code == 200
    body = commit.json()
    assert (body["status"], body["imported_count"]) == ("COMMITTED", 1)
    assert len(body["exceptions"]) == 1
    assert "Exame Fora Do Catalogo" in body["exceptions"][0]["message"]
    audit_sql = text(
        "SELECT COUNT(*) FROM audit_log WHERE entity_type = 'exam' "
        "AND action = 'exams.price_updated_from_price_table'"
    )
    with session_factory() as session:
        assert session.execute(audit_sql).scalar_one() == 1
    assert snapshot()[0] == 30

    listed = await client.get(f"/api/v1/imports/{pdf_batch_id}/exceptions")
    assert listed.status_code == 200
    assert len(listed.json()["exceptions"]) == 1

    # Reexecutar não duplica a exceção nem reaudita o preço já atualizado.
    again = await client.post(f"/api/v1/imports/{pdf_batch_id}/price-table/commit")
    assert (again.status_code, again.json()["imported_count"]) == (200, 0)
    with session_factory() as session:
        exceptions_count = session.execute(
            text("SELECT COUNT(*) FROM import_exceptions WHERE batch_id = :id"),
            {"id": pdf_batch_id},
        ).scalar_one()
        assert session.execute(audit_sql).scalar_one() == 1
    assert exceptions_count == 1


async def test_attendance_history_dry_run_commit_idempotency_and_permission(
    client: httpx.AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    await _login_as(client, session_factory, email="admin@vertere.local", role_id=ROLE_LAB_ADMIN)
    batch_id = await _run_full_cadastro_pipeline(client)

    dry_run = await client.post(f"/api/v1/imports/{batch_id}/attendances/dry-run")
    assert dry_run.status_code == 200
    dry_body = dry_run.json()
    assert dry_body["status"] == "DRY_RUN_DONE"
    assert (dry_body["imported_count"], dry_body["rejected_count"]) == (4, 1)
    assert dry_body["imported_grand_total"] == "390.00"
    with session_factory() as session:
        counts = session.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM attendances) AS attendances, "
                "(SELECT COUNT(*) FROM attendance_exams) AS items"
            )
        ).one()
    assert (counts.attendances, counts.items) == (0, 0)

    commit = await client.post(f"/api/v1/imports/{batch_id}/attendances/commit")
    assert commit.status_code == 200
    body = commit.json()
    assert body["status"] == "COMMITTED"
    assert (body["imported_count"], body["rejected_count"]) == (4, 1)
    assert body["imported_grand_total"] == "390.00"
    with session_factory() as session:
        rows = session.execute(
            text(
                "SELECT status, grand_total, protocol_number, legacy_protocol_reference, "
                "legacy_source_row_number, import_batch_id "
                "FROM attendances ORDER BY legacy_source_row_number"
            )
        ).all()
        item_count = session.execute(text("SELECT COUNT(*) FROM attendance_exams")).scalar_one()
        protocol_count = session.execute(
            text("SELECT COUNT(DISTINCT protocol_number) FROM attendances")
        ).scalar_one()
    assert len(rows) == 4
    assert item_count == 5  # 1 + 1 + 1 avulsos + 2 da linha combinada dividida
    assert protocol_count == 4  # cada um recebeu um protocolo real e distinto
    assert {row.status for row in rows} == {"COMPLETED"}
    assert {row.import_batch_id for row in rows} == {UUID(batch_id)}
    assert [row.legacy_protocol_reference for row in rows] == [
        "1/2026",
        "2/2026",
        "3/2026",
        "4/2026",
    ]
    assert [row.grand_total for row in rows] == [75, 120, 60, 135]

    # Reprocessar não duplica (`.claude/rules/10-data-migration.md`).
    again = await client.post(f"/api/v1/imports/{batch_id}/attendances/commit")
    assert again.status_code == 200
    assert (again.json()["imported_count"], again.json()["skipped_existing_count"]) == (0, 4)
    with session_factory() as session:
        assert session.execute(text("SELECT COUNT(*) FROM attendances")).scalar_one() == 4

    await _login_as(
        client, session_factory, email="technical@vertere.local", role_id=ROLE_TECHNICAL
    )
    forbidden = await client.post(f"/api/v1/imports/{batch_id}/attendances/commit")
    assert forbidden.status_code == 403
