"""Fase 4 — migrate the `Dados` (operational history) sheet into real
`AttendanceRecord`/`AttendanceExam` entities (`docs/01-analise-planilha.md`
§6, `.claude/rules/10-data-migration.md`).

Each valid row becomes exactly one migrated attendance, landing directly in
`COMPLETED` (`AttendanceRecord.create_from_legacy_import`) — never `DRAFT`,
never going through the live confirm flow. A row whose `Exame` cell combines
more than one panel (`"Check-up 2 + Urinálise"`) becomes one attendance with
one `AttendanceExam` per component, the row's real money split
proportionally by each component's *current* catalog price as a weight —
the weight only decides the split ratio, the actual charged amounts always
come from the row itself, never invented.

`on_call_fee` is always zero for migrated rows: the header-level flat fee
(`OnCallFeeSetting`) is a policy for attendances confirmed from now on. A
historical "Plantão" row already has whatever was actually charged folded
into its own `Adicional` column, snapshotted onto the item's
`surcharge_amount` — charging the current flat fee on top would double it.
`service_level` still gets tagged `PLANTAO_NORMAL` for a "Plantão" row
(the sheet has no way to distinguish normal/especial plantão), purely for
reporting/categorization — never used to compute money here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from app.modules.attendances.domain.entities import (
    AttendanceExam,
    AttendanceRecord,
    CollectionMethod,
    ServiceLevel,
)
from app.modules.attendances.domain.repositories import (
    AttendanceRepository,
    AttendanceSequenceRepository,
)
from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.domain.repositories import AuditLogWriter
from app.modules.catalog.domain.entities import Exam
from app.modules.catalog.domain.repositories import ExamRepository
from app.modules.clinics.domain.repositories import ClinicRepository
from app.modules.imports.application.text_normalization import derive_exam_code, split_owner_name
from app.modules.imports.domain.repositories import ImportStagingRowRepository
from app.modules.patients.domain.repositories import PatientRepository
from app.modules.veterinarians.domain.repositories import VeterinarianRepository
from app.shared.application.clock import Clock
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.money import round_currency

_REQUIRED_PERMISSION = "imports.execute"

SHEET_NAME = "Dados"
_FIRST_DATA_ROW = 5
_COLUMN_CLINIC = "A"
_COLUMN_DATE = "B"
_COLUMN_SEQUENCE = "E"
_COLUMN_LEGACY_PROTOCOL = "F"
_COLUMN_COLLECTION_METHOD = "G"
_COLUMN_VETERINARIAN = "H"
_COLUMN_PATIENT = "I"
_COLUMN_OWNER = "N"
_COLUMN_EXAM = "P"
_COLUMN_SERVICE_LEVEL = "Q"
_COLUMN_VALUE = "R"
_COLUMN_DISCOUNT = "S"
_COLUMN_SURCHARGE = "T"
_COLUMN_TOTAL = "U"

_EXCEL_EPOCH = date(1899, 12, 30)

_COLLECTION_METHOD_BY_LABEL = {
    "internos": CollectionMethod.INTERNAL,
    "motoboy": CollectionMethod.COURIER,
    "uber": CollectionMethod.UBER,
    "marli": CollectionMethod.MARLI,
    "helito/nicolas": CollectionMethod.HELITO_NICOLAS,
}

_SERVICE_LEVEL_BY_LABEL = {
    "normal": ServiceLevel.NORMAL,
    "plantão": ServiceLevel.PLANTAO_NORMAL,
    "plantao": ServiceLevel.PLANTAO_NORMAL,
}

_MONEY_TOLERANCE = Decimal("0.01")

# Combined-line components that are genuine abbreviations of an exam already
# named in full elsewhere in the catalog/price table — e.g. a row's `Exame`
# cell says "Renal 1 + Alt + Ast" where "Alt"/"Ast" are shorthand for the
# same "ALT"/"AST" the price table lists in full. Keyed by
# `derive_exam_code(abbreviation as it appears in the sheet)` -> the
# canonical exam name to re-resolve through the normal catalog lookup.
# Every entry here is a human-approved mapping (`.claude/rules/10-data-
# migration.md` step 6: "aplicar mapa de aliases aprovado por humano, nunca
# fuzzy match silencioso") — "CA"/"Ca" -> Cálcio, "CR" -> Creatinina,
# "UR" -> Ureia, "Hemogaso" -> Hemogasometria, bare "Pesquisa" -> Pesquisa
# de hemoparasitas, "Hemograma Doador" -> Hemograma (same price), bare "G"
# -> Glicose, and "Reti." -> Contagem de reticulócitos were all confirmed
# by the lab's own operator, not guessed.
_EXAM_NAME_ALIASES: dict[str, str] = {
    derive_exam_code("Alb"): "Albumina",
    derive_exam_code("CA"): "Cálcio",
    derive_exam_code("Ca"): "Cálcio",
    derive_exam_code("Cálcio Total"): "Cálcio",
    derive_exam_code("CR"): "Creatinina",
    derive_exam_code("UR"): "Ureia",
    derive_exam_code("Hemogaso"): "Hemogasometria",
    derive_exam_code("Pesquisa"): "Pesquisa de hemoparasitas",
    derive_exam_code("Hemograma Doador"): "Hemograma",
    derive_exam_code("Creat"): "Creatinina",
    derive_exam_code("Cai"): "Cálcio Iônico",
    derive_exam_code("Ca Ionico"): "Cálcio Iônico",
    derive_exam_code("Cl"): "Cloro",
    derive_exam_code("K"): "Potássio",
    derive_exam_code("Na"): "Sódio",
    derive_exam_code("P"): "Fósforo",
    derive_exam_code("PT"): "Proteínas Totais",
    derive_exam_code("CT"): "Colesterol Total",
    derive_exam_code("TG"): "Triglicerídeos",
    derive_exam_code("Trig"): "Triglicerídeos",
    derive_exam_code("Check3"): "Check-up 3",
    derive_exam_code("Hemog"): "Hemograma",
    derive_exam_code("Hemograna"): "Hemograma",
    derive_exam_code("P.O"): "Ponta de orelha",
    derive_exam_code("Urin."): "Urinálise",
    derive_exam_code("Cont Reticulocitos"): "Contagem de reticulócitos",
    derive_exam_code("Cont Reticulócitos"): "Contagem de reticulócitos",
    derive_exam_code("Contagem Reticulócitos"): "Contagem de reticulócitos",
    derive_exam_code("Contagem Retic."): "Contagem de reticulócitos",
    derive_exam_code("Contagem de Retic."): "Contagem de reticulócitos",
    derive_exam_code("Cont. Ret."): "Contagem de reticulócitos",
    derive_exam_code("Reticulócitos"): "Contagem de reticulócitos",
    derive_exam_code("(Reticulócitos Plantão)"): "Contagem de reticulócitos",
    derive_exam_code("Doador Adc."): "Doadores adicionais",
    derive_exam_code("Doad Add."): "Doadores adicionais",
    derive_exam_code("Pesq. Hemop"): "Pesquisa de hemoparasitas",
    derive_exam_code("Pesq. Hemop."): "Pesquisa de hemoparasitas",
    derive_exam_code("Pesq.Hemop"): "Pesquisa de hemoparasitas",
    derive_exam_code("Pesq. Hemoparasitas"): "Pesquisa de hemoparasitas",
    derive_exam_code("Pesquisa Hemoparasita"): "Pesquisa de hemoparasitas",
    derive_exam_code("Pesquisa Hemoparasitas"): "Pesquisa de hemoparasitas",
    derive_exam_code("Pesquisa de H."): "Pesquisa de hemoparasitas",
    derive_exam_code("Amostra adc"): "Amostra Adicional - Parasitológico",
    derive_exam_code("Amostra adicional"): "Amostra Adicional - Parasitológico",
    derive_exam_code("Parasitológico"): "Parasitológico de fezes",
    derive_exam_code("Rea.Cruz."): "Reação Cruzada",
    derive_exam_code("Rea Cruz"): "Reação Cruzada",
    derive_exam_code("Reaç.Cruz."): "Reação Cruzada",
    derive_exam_code("Glic"): "Glicose",
    derive_exam_code("Glu"): "Glicose",
    derive_exam_code("G"): "Glicose",
    derive_exam_code("Sangue Oculto"): "Pesquisa de Sangue Oculto",
    derive_exam_code("Reti."): "Contagem de reticulócitos",
    # Outsourced ("terceirizado") test — the lab's operator confirmed its
    # price (R$168,00) and it is now a real catalog exam under "Terceirizados".
    derive_exam_code("Urocultura"): "Urocultura e Antibiograma",
    derive_exam_code("Urocultura e Atb"): "Urocultura e Antibiograma",
    derive_exam_code("Urocultura/Antbg"): "Urocultura e Antibiograma",
    derive_exam_code("Antibiograma e Urocultura"): "Urocultura e Antibiograma",
    derive_exam_code("Cultura e Atb"): "Urocultura e Antibiograma",
    derive_exam_code("Cultura e ATB"): "Urocultura e Antibiograma",
    derive_exam_code("Cultura e Atbg"): "Urocultura e Antibiograma",
    derive_exam_code("Cult e antb"): "Urocultura e Antibiograma",
    derive_exam_code("Cultura Atb"): "Urocultura e Antibiograma",
    derive_exam_code("Uroc.Atb"): "Urocultura e Antibiograma",
    derive_exam_code("Urocul."): "Urocultura e Antibiograma",
    derive_exam_code("Centrifug (x2)"): "Centrifugação (x2)",
}

# Administrative fees typed into the `Exame` column alongside a real exam
# (e.g. `"Check-up 2 + Tx.Urgencia"`) rather than being their own priced
# catalog item — the official price table has no per-item price for these,
# only the flat plantão surcharge already captured in the row's own
# `Adicional` (`.claude/rules/10-data-migration.md`: never invent a price
# that doesn't exist). Excluded from the split entirely: the row's real
# money still goes in full to whichever real exam(s) remain.
_NON_EXAM_FEE_TOKENS: frozenset[str] = frozenset(
    derive_exam_code(token)
    for token in (
        "Taxa Coleta",
        "Tx coleta",
        "Tx Urgencia",
        "Tx urgencia",
        "Tx.Urgencia",
        "Taxa Plantão Hematócrito",
    )
)


# A single confirmed one-off ("foi algo pontual") — the lab's operator does
# not want this treated as a reusable rule: no catalog exam, no alias, no
# price to weight a split against. Kept out of `_KNOWN_OUTSOURCED_WITHOUT_
# PRICE` (that set stays an exception pending a real price) because the
# operator explicitly asked for the row to still be imported for historical
# continuity — so it is folded out of the split like a fee token instead,
# with the row's money landing on the remaining real component(s).
_HISTORICAL_ONE_OFF_COMPONENTS: frozenset[str] = frozenset({derive_exam_code("pH")})

# The history sheet's "Veterinário" column sometimes spells a name more (or
# less) fully than the master registry entry created from the cadastro-level
# import — e.g. a middle/maiden name included in one and abbreviated or
# dropped in the other. Each entry here was confirmed by the lab's operator
# as the exact same person, one candidate only (`.claude/rules/10-data-
# migration.md`: "aplicar mapa de aliases aprovado por humano, nunca fuzzy
# match silencioso") — keyed by the sheet's exact spelling (case-insensitive)
# -> the name the veterinarian is actually registered under.
_VETERINARIAN_NAME_ALIASES: dict[str, str] = {
    "bruna schütz rüdiger": "Bruna Rudiger",
    "elizandra regina g. mafra": "Elizandra G. Mafra",
    "michaela lopes leseux": "Michaela Lopes",
    "tanity greschechen petrys": "Tanity G. Petrys",
}


def _cell(raw_data: dict[str, object], column: str) -> str | None:
    value = raw_data.get(column)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _cell_decimal(raw_data: dict[str, object], column: str) -> Decimal | None:
    raw = _cell(raw_data, column)
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _excel_serial_to_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    try:
        serial = float(raw)
    except ValueError:
        return None
    return _EXCEL_EPOCH + timedelta(days=int(serial))


def _sort_key(raw_data: dict[str, object], *, fallback: int) -> tuple[int, int]:
    """Legacy `Nº` (column E) is the original entry order — reused directly
    instead of reconstructing it from the Data/Hora serials, since it *is*
    the order the legacy system itself assigned. Falls back to the staging
    row number for a row with no readable `Nº`, so it still sorts somewhere
    deterministic instead of raising."""
    raw = _cell(raw_data, _COLUMN_SEQUENCE)
    if raw is not None:
        try:
            return (0, int(float(raw)))
        except ValueError:
            pass
    return (1, fallback)


@dataclass(frozen=True, kw_only=True)
class ImportAttendanceHistoryCommand:
    actor_id: UUID | None
    actor_permissions: frozenset[str]
    batch_id: UUID


@dataclass(frozen=True, kw_only=True)
class ImportRowException:
    source_row_number: int
    message: str


@dataclass(frozen=True, kw_only=True)
class ImportAttendanceHistoryResult:
    imported_count: int
    skipped_existing_count: int
    rejected_count: int
    imported_grand_total: Decimal
    exceptions: tuple[ImportRowException, ...]


@dataclass(frozen=True, kw_only=True)
class _ItemPlan:
    exam: Exam
    value: Decimal
    discount: Decimal
    surcharge: Decimal


def _split_proportionally(*, total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Splits `total` across `len(weights)` parts proportional to each
    weight, remainder corrected on the last part so the parts always sum
    back to exactly `total` — the same "proporção + resto no último item"
    rule for every one of Valor/Desconto/Adicional, not just the headline
    value (`docs/01-analise-planilha.md` §6)."""
    weight_sum = sum(weights, Decimal("0"))
    if weight_sum == 0 or total == 0:
        return [Decimal("0")] * len(weights)
    parts = [round_currency(total * weight / weight_sum) for weight in weights[:-1]]
    parts.append(round_currency(total - sum(parts, Decimal("0"))))
    return parts


class ImportAttendanceHistoryUseCase:
    def __init__(
        self,
        *,
        staging_rows: ImportStagingRowRepository,
        attendances: AttendanceRepository,
        attendance_sequences: AttendanceSequenceRepository,
        clinics: ClinicRepository,
        veterinarians: VeterinarianRepository,
        patients: PatientRepository,
        exams: ExamRepository,
        audit: AuditLogWriter,
        clock: Clock,
    ) -> None:
        self._staging_rows = staging_rows
        self._attendances = attendances
        self._attendance_sequences = attendance_sequences
        self._clinics = clinics
        self._veterinarians = veterinarians
        self._patients = patients
        self._exams = exams
        self._audit = audit
        self._clock = clock

    def execute(self, command: ImportAttendanceHistoryCommand) -> ImportAttendanceHistoryResult:
        if _REQUIRED_PERMISSION not in command.actor_permissions:
            raise ForbiddenError(f"Permissão ausente: {_REQUIRED_PERMISSION}")

        rows = self._staging_rows.list_by_batch(command.batch_id, sheet_name=SHEET_NAME)
        data_rows = [row for row in rows if row.source_row_number >= _FIRST_DATA_ROW]
        data_rows.sort(key=lambda row: _sort_key(row.raw_data, fallback=row.source_row_number))

        clinic_ids_by_name = self._clinics.list_all_names()
        now = self._clock.now()

        imported = 0
        skipped = 0
        rejected = 0
        imported_total = Decimal("0")
        exceptions: list[ImportRowException] = []

        for row in data_rows:
            clinic_text = _cell(row.raw_data, _COLUMN_CLINIC)
            total = _cell_decimal(row.raw_data, _COLUMN_TOTAL)
            exam_text = _cell(row.raw_data, _COLUMN_EXAM)

            if total is None and exam_text is None:
                # Blank filler row past the real end of data, or a
                # footnote/legend row ("Observação:", "TOTAIS:" as a
                # section label rather than the residual-value row below) —
                # nothing to account for regardless of what column A says.
                continue

            if clinic_text is None:
                # The known "linha TOTAIS" residual case — a value with no
                # attendance behind it must never become a financial item
                # (`.claude/rules/10-data-migration.md`).
                rejected += 1
                exceptions.append(
                    ImportRowException(
                        source_row_number=row.source_row_number,
                        message=(
                            "Linha sem clínica/atendimento associado — valor residual "
                            f"({total if total is not None else '—'}) não importado como "
                            "item financeiro."
                        ),
                    )
                )
                continue

            existing = self._attendances.get_by_legacy_source(
                import_batch_id=command.batch_id, source_row_number=row.source_row_number
            )
            if existing is not None:
                skipped += 1
                continue

            outcome = self._import_row(
                row_number=row.source_row_number,
                raw_data=row.raw_data,
                clinic_text=clinic_text,
                clinic_ids_by_name=clinic_ids_by_name,
                batch_id=command.batch_id,
                actor_id=command.actor_id,
                now=now,
            )
            if outcome is None:
                continue
            if isinstance(outcome, ImportRowException):
                exceptions.append(outcome)
                continue
            imported += 1
            imported_total += outcome.grand_total

        return ImportAttendanceHistoryResult(
            imported_count=imported,
            skipped_existing_count=skipped,
            rejected_count=rejected,
            imported_grand_total=round_currency(imported_total),
            exceptions=tuple(exceptions),
        )

    def _import_row(
        self,
        *,
        row_number: int,
        raw_data: dict[str, object],
        clinic_text: str,
        clinic_ids_by_name: dict[str, UUID],
        batch_id: UUID,
        actor_id: UUID | None,
        now: datetime,
    ) -> AttendanceRecord | ImportRowException | None:
        def _exception(message: str) -> ImportRowException:
            return ImportRowException(source_row_number=row_number, message=message)

        clinic_id = clinic_ids_by_name.get(clinic_text.lower())
        if clinic_id is None:
            return _exception(f"Clínica '{clinic_text}' não encontrada no cadastro mestre.")

        service_date = _excel_serial_to_date(_cell(raw_data, _COLUMN_DATE))
        if service_date is None:
            return _exception("Data do atendimento ausente ou ilegível.")

        vet_text = _cell(raw_data, _COLUMN_VETERINARIAN)
        veterinarian = self._veterinarians.get_by_name(vet_text) if vet_text else None
        if veterinarian is None and vet_text is not None:
            alias_name = _VETERINARIAN_NAME_ALIASES.get(vet_text.strip().lower())
            if alias_name is not None:
                veterinarian = self._veterinarians.get_by_name(alias_name)
        if veterinarian is None:
            return _exception(f"Veterinário '{vet_text}' não encontrado no cadastro mestre.")

        patient_text = _cell(raw_data, _COLUMN_PATIENT)
        owner_raw = _cell(raw_data, _COLUMN_OWNER)
        patient = None
        if patient_text and owner_raw:
            owner_name = split_owner_name(owner_raw)
            patient = self._patients.get_by_owner_and_name(owner_name=owner_name, name=patient_text)
        if patient is None:
            return _exception(
                f"Paciente '{patient_text}' do proprietário '{owner_raw}' não encontrado no "
                "cadastro mestre."
            )

        method_text = (_cell(raw_data, _COLUMN_COLLECTION_METHOD) or "").lower()
        collection_method = _COLLECTION_METHOD_BY_LABEL.get(method_text)
        if collection_method is None:
            return _exception(f"Método de coleta '{method_text}' desconhecido.")

        level_text = (_cell(raw_data, _COLUMN_SERVICE_LEVEL) or "").lower()
        service_level = _SERVICE_LEVEL_BY_LABEL.get(level_text)
        if service_level is None:
            return _exception(f"Tipo de atendimento '{level_text}' desconhecido.")

        exam_text = _cell(raw_data, _COLUMN_EXAM)
        if exam_text is None:
            return _exception("Exame ausente.")

        value = _cell_decimal(raw_data, _COLUMN_VALUE)
        total = _cell_decimal(raw_data, _COLUMN_TOTAL)
        if value is None or total is None:
            return _exception("Valor ou Valor Total ausente/ilegível.")
        discount = _cell_decimal(raw_data, _COLUMN_DISCOUNT) or Decimal("0")
        surcharge = _cell_decimal(raw_data, _COLUMN_SURCHARGE) or Decimal("0")

        computed_total = round_currency(value - discount + surcharge)
        if abs(computed_total - total) > _MONEY_TOLERANCE:
            return _exception(
                f"Inconsistência aritmética: Valor ({value}) - Desconto ({discount}) + "
                f"Adicional ({surcharge}) = {computed_total}, mas Valor Total é {total}."
            )

        all_components = [part.strip() for part in exam_text.split("+") if part.strip()]
        if not all_components:
            return _exception("Exame ausente.")

        components = [
            component
            for component in all_components
            if derive_exam_code(component) not in _NON_EXAM_FEE_TOKENS
            and derive_exam_code(component) not in _HISTORICAL_ONE_OFF_COMPONENTS
        ]
        if not components:
            return _exception(
                f"Linha '{exam_text}' contém apenas taxas administrativas, sem exame real."
            )

        resolved: list[Exam] = []
        for component in components:
            code = derive_exam_code(component)
            exam = self._exams.get_by_code(code)
            if exam is None:
                alias_name = _EXAM_NAME_ALIASES.get(code)
                if alias_name is not None:
                    exam = self._exams.get_by_code(derive_exam_code(alias_name))
            if exam is None:
                return _exception(
                    f"Exame '{component}' (da linha '{exam_text}') não encontrado no catálogo."
                )
            resolved.append(exam)

        weights = [exam.price_base for exam in resolved]
        values = _split_proportionally(total=value, weights=weights)
        discounts = _split_proportionally(total=discount, weights=weights)
        surcharges = _split_proportionally(total=surcharge, weights=weights)

        plans = [
            _ItemPlan(exam=exam, value=item_value, discount=item_discount, surcharge=item_surcharge)
            for exam, item_value, item_discount, item_surcharge in zip(
                resolved, values, discounts, surcharges, strict=True
            )
        ]

        attendance_id = uuid4()
        try:
            items = [
                AttendanceExam(
                    id=uuid4(),
                    attendance_id=attendance_id,
                    exam_id=plan.exam.id,
                    exam_code=str(plan.exam.code),
                    exam_name=plan.exam.name,
                    price_base=plan.value,
                    quantity=1,
                    discount_amount=plan.discount,
                    surcharge_amount=plan.surcharge,
                )
                for plan in plans
            ]
        except ValueError as exc:
            return _exception(f"Item de exame inválido: {exc}")

        items_total = round_currency(sum((item.total_amount for item in items), Decimal("0")))
        if abs(items_total - total) > _MONEY_TOLERANCE:
            return _exception(
                f"Divisão proporcional do valor combinado ('{exam_text}') não reproduziu o "
                f"Valor Total da linha ({total} vs. {items_total} calculado)."
            )

        protocol_year = service_date.year
        protocol_sequence = self._attendance_sequences.next_sequence(protocol_year)

        try:
            attendance = AttendanceRecord.create_from_legacy_import(
                id=attendance_id,
                clinic_id=clinic_id,
                veterinarian_id=veterinarian.id,
                patient_id=patient.id,
                collection_method=collection_method,
                service_level=service_level,
                service_date=service_date,
                items=items,
                protocol_year=protocol_year,
                protocol_sequence=protocol_sequence,
                on_call_fee=Decimal("0"),
                legacy_source_row_number=row_number,
                legacy_protocol_reference=_cell(raw_data, _COLUMN_LEGACY_PROTOCOL),
                import_batch_id=batch_id,
                now=now,
                created_by=actor_id,
            )
        except ValueError as exc:
            return _exception(f"Atendimento inválido: {exc}")

        self._attendances.add(attendance)
        self._audit.record(
            AuditEntry(
                actor_user_id=actor_id,
                actor_scope=ActorScope.LAB,
                action="attendances.imported_from_history",
                entity_type="attendance",
                entity_id=str(attendance.id),
                after_state={
                    "protocol_number": attendance.protocol_number,
                    "legacy_protocol_reference": attendance.legacy_protocol_reference,
                    "grand_total": str(attendance.grand_total),
                },
            )
        )
        return attendance
