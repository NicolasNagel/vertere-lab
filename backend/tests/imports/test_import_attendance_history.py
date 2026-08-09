from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.attendances.domain.entities import AttendanceStatus, ServiceLevel
from app.modules.catalog.domain.entities import Exam, ExamStatus
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.clinics.domain.entities import Clinic
from app.modules.imports.application.import_attendance_history import (
    SHEET_NAME,
    ImportAttendanceHistoryCommand,
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


def test_without_permission_is_forbidden() -> None:
    fixture = _Fixture()
    command = ImportAttendanceHistoryCommand(
        actor_id=uuid4(), actor_permissions=frozenset(), batch_id=fixture.batch_id
    )
    with pytest.raises(ForbiddenError):
        fixture.use_case().execute(command)


def test_single_exam_row_is_imported_as_completed_with_matching_totals() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Hemograma", price_base="75.00")
    fixture.stage_row(5, fixture.base_row(exam="Hemograma", value="75.00", total="75.00"))

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    assert result.exceptions == ()
    assert result.imported_grand_total == Decimal("75.00")

    [attendance] = list(fixture.attendances._attendances.values())
    assert attendance.status == AttendanceStatus.COMPLETED
    assert attendance.grand_total == Decimal("75.00")
    assert attendance.legacy_source_row_number == 5
    assert attendance.legacy_protocol_reference == "1/2026"
    assert attendance.protocol_number == "2026/000001"
    assert len(attendance.items) == 1
    assert attendance.items[0].exam_name == "Hemograma"


def test_row_with_discount_and_surcharge_reproduces_the_recorded_total() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Check-up 2", price_base="120.00")
    fixture.stage_row(
        5,
        fixture.base_row(
            exam="Check-up 2", value="120.00", discount="10.00", surcharge="5.00", total="115.00"
        ),
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    [attendance] = list(fixture.attendances._attendances.values())
    assert attendance.grand_total == Decimal("115.00")
    assert attendance.discount_total == Decimal("10.00")
    assert attendance.surcharge_total == Decimal("5.00")
    assert attendance.on_call_fee == Decimal("0")


def test_combined_line_splits_proportionally_by_catalog_price_weight() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Check-up 2", price_base="120.00")
    fixture.add_exam(name="Urinálise", price_base="60.00")
    # Real recorded total for the combo is 165.00 (a discount was applied to
    # the bundle) — weights are 120:60 = 2:1, so the split must be 110/55,
    # not the raw catalog prices.
    fixture.stage_row(
        5,
        fixture.base_row(exam="Check-up 2 + Urinálise", value="165.00", total="165.00"),
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    [attendance] = list(fixture.attendances._attendances.values())
    assert attendance.grand_total == Decimal("165.00")
    assert len(attendance.items) == 2
    values = sorted(item.price_base for item in attendance.items)
    assert values == [Decimal("55.00"), Decimal("110.00")]


def test_plantao_row_tags_service_level_but_never_adds_a_header_on_call_fee() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Hemograma", price_base="75.00")
    fixture.stage_row(
        5,
        fixture.base_row(
            exam="Hemograma",
            value="97.50",
            surcharge="22.50",
            total="120.00",
            service_level="Plantão",
        ),
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    [attendance] = list(fixture.attendances._attendances.values())
    assert attendance.service_level == ServiceLevel.PLANTAO_NORMAL
    assert attendance.on_call_fee == Decimal("0")
    assert attendance.grand_total == Decimal("120.00")


def test_residual_row_with_no_clinic_is_rejected_never_imported() -> None:
    fixture = _Fixture()
    fixture.stage_row(
        2502,
        {
            "A": None,
            "B": None,
            "P": None,
            "R": None,
            "S": None,
            "T": None,
            "U": "100.00",
        },
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert result.rejected_count == 1
    assert result.imported_grand_total == Decimal("0")


def test_fully_blank_row_is_silently_skipped() -> None:
    fixture = _Fixture()
    fixture.stage_row(2600, {"A": None, "P": None, "U": None})

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert result.rejected_count == 0
    assert result.exceptions == ()


def test_footnote_row_with_only_a_label_is_silently_skipped() -> None:
    """Real spreadsheet has a trailing "Observação:" row with text in
    column A but nothing else — must not be treated as an unresolved
    clinic name."""
    fixture = _Fixture()
    fixture.stage_row(4006, {"A": "Observação:", "P": None, "U": None})

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert result.rejected_count == 0
    assert result.exceptions == ()


def test_arithmetic_mismatch_becomes_an_exception_never_guessed() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Hemograma", price_base="75.00")
    fixture.stage_row(
        5,
        fixture.base_row(exam="Hemograma", value="113.00", total="135.00"),
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert "Inconsistência aritmética" in result.exceptions[0].message


def test_unknown_clinic_becomes_an_exception_never_created_silently() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Hemograma", price_base="75.00")
    fixture.stage_row(
        5,
        fixture.base_row(
            clinic="Clínica Desconhecida", exam="Hemograma", value="75.00", total="75.00"
        ),
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert "não encontrada" in result.exceptions[0].message
    assert fixture.clinics.get_by_name("Clínica Desconhecida") is None


def test_unmatched_combo_component_rejects_the_whole_line() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Check-up 2", price_base="120.00")
    # "Urinálise" never added to the catalog.
    fixture.stage_row(
        5, fixture.base_row(exam="Check-up 2 + Urinálise", value="165.00", total="165.00")
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert "não encontrado no catálogo" in result.exceptions[0].message


def test_abbreviated_component_resolves_via_alias_to_the_full_catalog_exam() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Check-up 2", price_base="120.00")
    fixture.add_exam(name="Creatinina", price_base="20.00")
    # Sheet shorthand "Creat" for "Creatinina" — a confirmed unambiguous
    # abbreviation, not a guess (`_EXAM_NAME_ALIASES`).
    fixture.stage_row(
        5, fixture.base_row(exam="Check-up 2 + Creat", value="140.00", total="140.00")
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    [attendance] = list(fixture.attendances._attendances.values())
    assert {item.exam_name for item in attendance.items} == {"Check-up 2", "Creatinina"}


def test_administrative_fee_token_is_excluded_from_the_combo_split() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Check-up 2", price_base="120.00")
    # "Tx.Urgencia" is not a priced catalog item — the whole recorded value
    # belongs to the one real exam in the line.
    fixture.stage_row(
        5, fixture.base_row(exam="Check-up 2 + Tx.Urgencia", value="120.00", total="120.00")
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    [attendance] = list(fixture.attendances._attendances.values())
    assert len(attendance.items) == 1
    assert attendance.items[0].exam_name == "Check-up 2"
    assert attendance.items[0].price_base == Decimal("120.00")


def test_line_with_only_fee_tokens_and_no_real_exam_becomes_an_exception() -> None:
    fixture = _Fixture()
    fixture.stage_row(5, fixture.base_row(exam="Tx.Urgencia", value="20.00", total="20.00"))

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert "taxas administrativas" in result.exceptions[0].message


def test_genuinely_ambiguous_abbreviation_still_becomes_an_exception() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Ureia", price_base="23.00")
    # "CRE" is not covered by any alias — must never be guessed
    # (`.claude/rules/10-data-migration.md`: "nenhum merge incerto automático").
    fixture.stage_row(5, fixture.base_row(exam="CRE", value="23.00", total="23.00"))

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert len(result.exceptions) == 1
    assert "não encontrado no catálogo" in result.exceptions[0].message


def test_ph_is_a_one_off_folded_out_of_the_split_but_the_row_still_imports() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Check-up 2", price_base="120.00")
    fixture.add_exam(name="Sedimentoscopia", price_base="15.00")
    # Confirmed by the operator as a genuine one-off, not a rule to reuse:
    # no catalog exam, no alias — "pH" is folded out of the split like a fee
    # token so the row is still kept for historical continuity.
    fixture.stage_row(
        5,
        fixture.base_row(exam="Check-up 2+Sedimentoscopia+pH", value="135.00", total="135.00"),
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    [attendance] = list(fixture.attendances._attendances.values())
    assert {item.exam_name for item in attendance.items} == {
        "Check-up 2",
        "Sedimentoscopia",
    }
    assert attendance.grand_total == Decimal("135.00")


@pytest.mark.parametrize(
    ("abbreviation", "canonical_name"),
    [
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
    ],
)
def test_operator_confirmed_abbreviations_resolve_via_alias(
    abbreviation: str, canonical_name: str
) -> None:
    fixture = _Fixture()
    fixture.add_exam(name=canonical_name, price_base="30.00")
    fixture.stage_row(5, fixture.base_row(exam=abbreviation, value="30.00", total="30.00"))

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    [attendance] = list(fixture.attendances._attendances.values())
    assert attendance.items[0].exam_name == canonical_name


def test_outsourced_urocultura_family_resolves_now_that_a_price_is_confirmed() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Urinálise", price_base="35.00")
    fixture.add_exam(name="Urocultura e Antibiograma", price_base="168.00")
    # Confirmed by the lab's operator: R$168,00, now a real catalog exam
    # under "Terceirizados" — no longer an unresolved exception.
    fixture.stage_row(
        5, fixture.base_row(exam="Urinálise + Urocultura", value="203.00", total="203.00")
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    [attendance] = list(fixture.attendances._attendances.values())
    assert {item.exam_name for item in attendance.items} == {
        "Urinálise",
        "Urocultura e Antibiograma",
    }


def test_reimporting_the_same_batch_does_not_duplicate() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Hemograma", price_base="75.00")
    fixture.stage_row(5, fixture.base_row(exam="Hemograma", value="75.00", total="75.00"))

    first = fixture.use_case().execute(fixture.command())
    second = fixture.use_case().execute(fixture.command())

    assert first.imported_count == 1
    assert second.imported_count == 0
    assert second.skipped_existing_count == 1
    assert len(fixture.attendances._attendances) == 1


def test_unknown_veterinarian_becomes_an_exception() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Hemograma", price_base="75.00")
    fixture.stage_row(
        5, fixture.base_row(vet="Dr. Desconhecido", exam="Hemograma", value="75.00", total="75.00")
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert "Veterinário" in result.exceptions[0].message


def test_operator_confirmed_veterinarian_name_variant_resolves_via_alias() -> None:
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

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 1
    [attendance] = list(fixture.attendances._attendances.values())
    assert attendance.veterinarian_id == fuller_vet.id


def test_unknown_patient_owner_pair_becomes_an_exception() -> None:
    fixture = _Fixture()
    fixture.add_exam(name="Hemograma", price_base="75.00")
    fixture.stage_row(
        5,
        fixture.base_row(
            patient="Rex", owner="Outra Pessoa", exam="Hemograma", value="75.00", total="75.00"
        ),
    )

    result = fixture.use_case().execute(fixture.command())

    assert result.imported_count == 0
    assert "Paciente" in result.exceptions[0].message
