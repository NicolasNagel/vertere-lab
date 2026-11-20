from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.attendances.domain.entities import (
    AttendanceRecord,
    AttendanceStatus,
    ServiceLevel,
)
from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.clinics.domain.entities import Clinic
from app.modules.imports.application.import_attendance_history import (
    SHEET_NAME,
    ImportAttendanceHistoryCommand,
    ImportAttendanceHistoryResult,
    ImportAttendanceHistoryUseCase,
)
from app.modules.imports.application.text_normalization import derive_exam_code
from app.modules.patients.domain.entities import Patient, PatientSex
from app.modules.veterinarians.domain.entities import Veterinarian
from app.modules.veterinarians.domain.value_objects import Crmv
from app.shared.domain.errors import ForbiddenError
from tests.attendances.fakes import FakeAttendanceRepository, FakeAttendanceSequenceRepository
from tests.catalog.fakes import FakeExamRepository
from tests.imports.fakes import FakeImportStagingRowRepository, make_staging_row
from tests.patients.fakes import FakePatientRepository
from tests.veterinarian_clinics.fakes import FakeAuditLogWriter, FakeClinicRepository
from tests.veterinarian_clinics.fakes import FakeVeterinarianRepository as _FakeVetRepo

_NOW = datetime(2026, 8, 1, tzinfo=UTC)
_SEED_AT = datetime(2026, 1, 1, tzinfo=UTC)

# Excel serial for 2026-01-03 (days since 1899-12-30).
_SERIAL_2026_01_03 = "46025"


def _actor() -> frozenset[str]:
    return frozenset({"imports.execute"})


class _Fixture:
    def __init__(self) -> None:
        self.batch_id = uuid4()
        self.staging_rows = FakeImportStagingRowRepository()
        self.attendances = FakeAttendanceRepository()
        self.sequences = FakeAttendanceSequenceRepository()
        self.clinics = FakeClinicRepository()
        self.veterinarians = _FakeVetRepo()
        self.patients = FakePatientRepository()
        self.exams = FakeExamRepository()
        self.audit = FakeAuditLogWriter()

        self.clinic = Clinic(
            id=uuid4(), name="Schweitzer", created_at=_SEED_AT, updated_at=_SEED_AT
        )
        self.clinics.add(self.clinic)

        self.vet = Veterinarian(
            id=uuid4(),
            name="Dra. Ana",
            crmv=Crmv("CRMV-SC 1234"),
            created_at=_SEED_AT,
            updated_at=_SEED_AT,
        )
        self.veterinarians.add(self.vet)

        self.patient = Patient(
            id=uuid4(),
            name="Rex",
            species_id=uuid4(),
            sex=PatientSex.MALE,
            owner_name="Maria",
            created_at=_SEED_AT,
            updated_at=_SEED_AT,
        )
        self.patients.add(self.patient)

    def add_exam(self, *, name: str, price_base: str) -> Exam:
        exam = Exam(
            id=uuid4(),
            code=ExamCode(derive_exam_code(name)),
            name=name,
            category_id=uuid4(),
            price_base=Decimal(price_base),
            species_ids=frozenset({uuid4()}),
            status=ExamStatus.ACTIVE,
            created_at=_SEED_AT,
            updated_at=_SEED_AT,
        )
        self.exams.add(exam)
        return exam

    def stage_row(self, row_number: int, raw_data: dict[str, object]) -> None:
        self.staging_rows.add_many(
            [
                make_staging_row(
                    batch_id=self.batch_id,
                    sheet_name=SHEET_NAME,
                    source_row_number=row_number,
                    raw_data=raw_data,
                )
            ]
        )

    def base_row(
        self,
        *,
        clinic: str | None = "Schweitzer",
        vet: str | None = "Dra. Ana",
        patient: str | None = "Rex",
        owner: str | None = "Maria",
        exam: str | None,
        value: str | None,
        discount: str | None = None,
        surcharge: str | None = None,
        total: str | None,
        service_level: str = "Normal",
        collection_method: str = "Internos",
        legacy_protocol: str | None = "1/2026",
        sequence: str | None = "1",
        date_serial: str | None = _SERIAL_2026_01_03,
    ) -> dict[str, object]:
        return {
            "A": clinic,
            "B": date_serial,
            "E": sequence,
            "F": legacy_protocol,
            "G": collection_method,
            "H": vet,
            "I": patient,
            "N": owner,
            "P": exam,
            "Q": service_level,
            "R": value,
            "S": discount,
            "T": surcharge,
            "U": total,
        }

    def use_case(self) -> ImportAttendanceHistoryUseCase:
        return ImportAttendanceHistoryUseCase(
            staging_rows=self.staging_rows,
            attendances=self.attendances,
            attendance_sequences=self.sequences,
            clinics=self.clinics,
            veterinarians=self.veterinarians,
            patients=self.patients,
            exams=self.exams,
            audit=self.audit,
            clock=type("_C", (), {"now": staticmethod(lambda: _NOW)})(),
        )

    def command(self) -> ImportAttendanceHistoryCommand:
        return ImportAttendanceHistoryCommand(
            actor_id=uuid4(), actor_permissions=_actor(), batch_id=self.batch_id
        )


def _import_one(
    exams: dict[str, str], **row: str
) -> tuple[_Fixture, ImportAttendanceHistoryResult]:
    """Run the import for one staged row against a catalog of `{name: price}` exams."""
    fixture = _Fixture()
    for name, price in exams.items():
        fixture.add_exam(name=name, price_base=price)
    fixture.stage_row(5, fixture.base_row(**row))
    return fixture, fixture.use_case().execute(fixture.command())


def _only_attendance(fixture: _Fixture) -> AttendanceRecord:
    [attendance] = list(fixture.attendances._attendances.values())
    return attendance


def test_import_requires_permission_and_is_idempotent_per_batch() -> None:
    fixture = _Fixture()
    with pytest.raises(ForbiddenError):
        fixture.use_case().execute(
            ImportAttendanceHistoryCommand(
                actor_id=uuid4(), actor_permissions=frozenset(), batch_id=fixture.batch_id
            )
        )

    fixture.add_exam(name="Hemograma", price_base="75.00")
    fixture.stage_row(5, fixture.base_row(exam="Hemograma", value="75.00", total="75.00"))
    first = fixture.use_case().execute(fixture.command())
    second = fixture.use_case().execute(fixture.command())

    assert (first.imported_count, first.exceptions) == (1, ())
    assert first.imported_grand_total == Decimal("75.00")
    assert (second.imported_count, second.skipped_existing_count) == (0, 1)
    assert len(fixture.attendances._attendances) == 1

    attendance = _only_attendance(fixture)
    assert attendance.status == AttendanceStatus.COMPLETED
    assert attendance.grand_total == Decimal("75.00")
    assert attendance.legacy_source_row_number == 5
    assert attendance.legacy_protocol_reference == "1/2026"
    assert attendance.protocol_number == "P000001/26"
    assert [item.exam_name for item in attendance.items] == ["Hemograma"]


def test_import_reproduces_recorded_totals_for_discounts_surcharges_and_combos() -> None:
    fixture, result = _import_one(
        {"Check-up 2": "120.00"},
        exam="Check-up 2",
        value="120.00",
        discount="10.00",
        surcharge="5.00",
        total="115.00",
    )
    attendance = _only_attendance(fixture)
    assert result.imported_count == 1
    assert (attendance.grand_total, attendance.discount_total, attendance.surcharge_total) == (
        Decimal("115.00"),
        Decimal("10.00"),
        Decimal("5.00"),
    )
    assert attendance.on_call_fee == Decimal("0")

    # Combo: o total gravado (165) é repartido pelo peso do preço de catálogo (120:60 = 110/55).
    fixture, result = _import_one(
        {"Check-up 2": "120.00", "Urinálise": "60.00"},
        exam="Check-up 2 + Urinálise",
        value="165.00",
        total="165.00",
    )
    attendance = _only_attendance(fixture)
    assert attendance.grand_total == Decimal("165.00")
    assert sorted(item.price_base for item in attendance.items) == [
        Decimal("55.00"),
        Decimal("110.00"),
    ]

    # Plantão marca o nível de serviço, mas nunca cria taxa de plantão no cabeçalho.
    fixture, _ = _import_one(
        {"Hemograma": "75.00"},
        exam="Hemograma",
        value="97.50",
        surcharge="22.50",
        total="120.00",
        service_level="Plantão",
    )
    attendance = _only_attendance(fixture)
    assert attendance.service_level == ServiceLevel.PLANTAO_NORMAL
    assert (attendance.on_call_fee, attendance.grand_total) == (Decimal("0"), Decimal("120.00"))


def test_import_resolves_aliases_fee_tokens_and_one_offs_in_exam_names() -> None:
    # (catálogo, texto da planilha, valor, exames esperados)
    cases: list[tuple[dict[str, str], str, str, set[str]]] = [
        (
            {"Check-up 2": "120.00", "Creatinina": "20.00"},
            "Check-up 2 + Creat",
            "140.00",
            {"Check-up 2", "Creatinina"},
        ),
        ({"Check-up 2": "120.00"}, "Check-up 2 + Tx.Urgencia", "120.00", {"Check-up 2"}),
        (
            {"Check-up 2": "120.00", "Sedimentoscopia": "15.00"},
            "Check-up 2+Sedimentoscopia+pH",
            "135.00",
            {"Check-up 2", "Sedimentoscopia"},
        ),
        (
            {"Urinálise": "35.00", "Urocultura e Antibiograma": "168.00"},
            "Urinálise + Urocultura",
            "203.00",
            {"Urinálise", "Urocultura e Antibiograma"},
        ),
    ]
    for catalog, sheet_text, value, expected in cases:
        fixture, result = _import_one(catalog, exam=sheet_text, value=value, total=value)
        assert result.imported_count == 1, sheet_text
        attendance = _only_attendance(fixture)
        assert {item.exam_name for item in attendance.items} == expected, sheet_text
        assert attendance.grand_total == Decimal(value), sheet_text

    # Abreviações confirmadas pelo operador resolvem para o exame de catálogo.
    for abbreviation, canonical in (
        ("CA", "Cálcio"),
        ("Ca", "Cálcio"),
        ("CR", "Creatinina"),
        ("UR", "Ureia"),
        ("Hemogaso", "Hemogasometria"),
        ("Pesquisa", "Pesquisa de hemoparasitas"),
        ("Hemograma Doador", "Hemograma"),
        ("G", "Glicose"),
        ("Reti.", "Contagem de reticulócitos"),
        ("Cálcio Total", "Cálcio"),
        ("Centrifug (x2)", "Centrifugação (x2)"),
        ("Taxa Plantão Hematócrito", "Hematócrito"),
    ):
        fixture, result = _import_one(
            {canonical: "30.00"}, exam=abbreviation, value="30.00", total="30.00"
        )
        assert result.imported_count == 1, abbreviation
        assert _only_attendance(fixture).items[0].exam_name == canonical, abbreviation

    # O veterinário também resolve por variante de nome confirmada.
    fixture = _Fixture()
    fixture.add_exam(name="Hemograma", price_base="75.00")
    fuller_vet = Veterinarian(
        id=uuid4(),
        name="Michaela Lopes",
        crmv=Crmv("CRMV-SC 14245"),
        created_at=_SEED_AT,
        updated_at=_SEED_AT,
    )
    fixture.veterinarians.add(fuller_vet)
    fixture.stage_row(
        5,
        fixture.base_row(
            vet="Michaela Lopes Leseux", exam="Hemograma", value="75.00", total="75.00"
        ),
    )
    assert fixture.use_case().execute(fixture.command()).imported_count == 1
    assert _only_attendance(fixture).veterinarian_id == fuller_vet.id


def test_import_turns_unresolvable_rows_into_exceptions_and_skips_non_data_rows() -> None:
    hemograma = {"Hemograma": "75.00"}
    plain = {"exam": "Hemograma", "value": "75.00", "total": "75.00"}
    # (catálogo, campos da linha, trecho esperado da mensagem)
    rejected: list[tuple[dict[str, str], dict[str, str], str]] = [
        (
            hemograma,
            {"exam": "Hemograma", "value": "113.00", "total": "135.00"},
            "Inconsistência aritmética",
        ),
        (hemograma, {**plain, "clinic": "Clínica Desconhecida"}, "não encontrada"),
        (
            {"Check-up 2": "120.00"},
            {"exam": "Check-up 2 + Urinálise", "value": "165.00", "total": "165.00"},
            "não encontrado no catálogo",
        ),
        ({}, {"exam": "Tx.Urgencia", "value": "20.00", "total": "20.00"}, "taxas administrativas"),
        (
            {"Ureia": "23.00"},
            {"exam": "CRE", "value": "23.00", "total": "23.00"},  # abreviação ambígua: nunca chuta
            "não encontrado no catálogo",
        ),
        (hemograma, {**plain, "vet": "Dr. Desconhecido"}, "Veterinário"),
        (hemograma, {**plain, "owner": "Outra Pessoa"}, "Paciente"),
    ]
    for catalog, row, message in rejected:
        fixture, result = _import_one(catalog, **row)
        assert result.imported_count == 0, message
        assert len(result.exceptions) == 1, message
        assert message in result.exceptions[0].message
        assert not fixture.attendances._attendances
        assert fixture.clinics.get_by_name("Clínica Desconhecida") is None  # nunca cria em silêncio

    # Linha residual sem clínica é rejeitada; linha em branco e nota de rodapé são ignoradas.
    fixture = _Fixture()
    fixture.stage_row(
        2502, {"A": None, "B": None, "P": None, "R": None, "S": None, "T": None, "U": "100.00"}
    )
    fixture.stage_row(2600, {"A": None, "P": None, "U": None})
    fixture.stage_row(4006, {"A": "Observação:", "P": None, "U": None})
    result = fixture.use_case().execute(fixture.command())
    assert (result.imported_count, result.rejected_count) == (0, 1)
    assert result.imported_grand_total == Decimal("0")
    assert [row.source_row_number for row in result.exceptions] == [2502]  # só a residual


def test_import_turns_nan_infinity_and_oversized_values_into_row_exceptions() -> None:
    """NaN crashed `round_currency` and a value past NUMERIC(14,2) aborted the insert: the whole
    import died instead of leaving one exception per bad row."""
    for bad in ("NaN", "Infinity", "1E+20", "-Infinity"):
        fixture, result = _import_one(
            {"Hemograma": "75.00"}, exam="Hemograma", value=bad, total=bad
        )
        assert result.imported_count == 0, bad
        assert len(result.exceptions) == 1, bad
        assert not fixture.attendances._attendances
