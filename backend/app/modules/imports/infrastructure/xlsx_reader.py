"""Minimal `.xlsx` (OOXML) reader — stdlib only.

No `openpyxl`/`pandas` dependency: an `.xlsx` file is a zip of XML parts, and
reading raw cell values only requires `zipfile` + `xml.etree`
(`.claude/rules/00-global.md` — "não adicione biblioteca para função trivial
que a stdlib/stack já resolve"). This reader is intentionally dumb — it does
not infer headers, skip blank rows, or coerce types. Staging must load the
original content unmodified (`.claude/rules/10-data-migration.md`, step 3:
"carregar em staging sem transformar o conteúdo original"); interpretation
happens in the normalization use cases that read from staging afterwards.

Numeric/date cells come back as the raw string stored in the XML (Excel
serial numbers for dates, plain numbers as text) — never coerced here.

Decompressed-size guard: found via QA against a running instance — a
192 KB upload (well under the router's 20 MB compressed-size cap) can carry
a `sharedStrings.xml` that decompresses to ~190 MB (a classic zip-bomb
shape: one long repeated string, which DEFLATE compresses extremely well).
The compressed-size check alone never sees this; it only bounds what
crosses the wire, not what `zipfile` inflates into memory afterward. Each
part is checked against its *declared* uncompressed size
(`ZipInfo.file_size`, cheap metadata read, no decompression needed) before
`archive.read()` ever runs.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
_PKG_REL_NS = {"pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
_CELL_REF_PATTERN = re.compile(r"([A-Z]+)\d+")

# Generous headroom above what any real spreadsheet part needs (the actual
# source planilha's largest part is a few MB), far below what would let a
# single request exhaust server memory.
_MAX_UNCOMPRESSED_PART_SIZE = 200 * 1024 * 1024  # 200 MB


class InvalidXlsxError(ValueError):
    pass


@dataclass(frozen=True, kw_only=True)
class XlsxRow:
    row_number: int
    cells: dict[str, str | None]


@dataclass(frozen=True, kw_only=True)
class XlsxSheet:
    name: str
    rows: tuple[XlsxRow, ...]


def _safe_read(archive: zipfile.ZipFile, name: str) -> bytes:
    info = archive.getinfo(name)
    if info.file_size > _MAX_UNCOMPRESSED_PART_SIZE:
        raise InvalidXlsxError(
            f"Parte '{name}' do arquivo excede o tamanho descomprimido máximo permitido."
        )
    return archive.read(info)


def read_workbook(content: bytes) -> tuple[XlsxSheet, ...]:
    """Parse every visible-or-not sheet in an `.xlsx` file, in workbook order."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise InvalidXlsxError("Arquivo não é um .xlsx válido.") from exc

    with archive:
        try:
            shared_strings = _read_shared_strings(archive)
            sheet_targets = _read_sheet_targets(archive)
        except (KeyError, ET.ParseError) as exc:
            raise InvalidXlsxError("Estrutura interna do .xlsx inesperada.") from exc

        sheets: list[XlsxSheet] = []
        for name, target in sheet_targets:
            try:
                data = _safe_read(archive, f"xl/{target}")
            except KeyError as exc:
                raise InvalidXlsxError(
                    f"Aba '{name}' referenciada mas ausente no arquivo."
                ) from exc
            rows = _read_sheet_rows(data, shared_strings)
            sheets.append(XlsxSheet(name=name, rows=rows))
        return tuple(sheets)


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(_safe_read(archive, "xl/sharedStrings.xml"))
    strings: list[str] = []
    for si in root.findall("m:si", _NS):
        # A shared string can be a single <t> or a run of <r><t>…</t></r>.
        text_parts = [
            t.text or ""
            for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        ]
        strings.append("".join(text_parts))
    return strings


def _read_sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    """Map declared sheet name -> relative path (e.g. 'worksheets/sheet3.xml'),
    resolved through workbook.xml.rels so declaration order in workbook.xml
    (not the sheetN.xml filename) is what determines the returned order."""
    workbook_root = ET.fromstring(_safe_read(archive, "xl/workbook.xml"))
    rels_root = ET.fromstring(_safe_read(archive, "xl/_rels/workbook.xml.rels"))

    rid_to_target = {
        rel.get("Id"): rel.get("Target")
        for rel in rels_root.findall("pr:Relationship", _PKG_REL_NS)
    }

    targets: list[tuple[str, str]] = []
    for sheet_el in workbook_root.findall("m:sheets/m:sheet", _NS):
        name = sheet_el.get("name") or ""
        rid = sheet_el.get(f"{{{_REL_NS['r']}}}id")
        target = rid_to_target.get(rid or "")
        if target is None:
            continue
        targets.append((name, target))
    return targets


def _read_sheet_rows(sheet_xml: bytes, shared_strings: list[str]) -> tuple[XlsxRow, ...]:
    root = ET.fromstring(sheet_xml)
    sheet_data = root.find("m:sheetData", _NS)
    if sheet_data is None:
        return ()

    rows: list[XlsxRow] = []
    for row_el in sheet_data.findall("m:row", _NS):
        row_number_raw = row_el.get("r")
        row_number = int(row_number_raw) if row_number_raw else len(rows) + 1
        cells: dict[str, str | None] = {}
        for cell_el in row_el.findall("m:c", _NS):
            ref = cell_el.get("r") or ""
            match = _CELL_REF_PATTERN.match(ref)
            column = match.group(1) if match else ref
            cell_type = cell_el.get("t")
            value_el = cell_el.find("m:v", _NS)
            raw_value = value_el.text if value_el is not None else None
            if cell_type == "s" and raw_value is not None:
                index = int(raw_value)
                raw_value = shared_strings[index] if index < len(shared_strings) else None
            elif cell_type == "inlineStr":
                inline_text_el = cell_el.find("m:is/m:t", _NS)
                raw_value = inline_text_el.text if inline_text_el is not None else None
            cells[column] = raw_value
        rows.append(XlsxRow(row_number=row_number, cells=cells))
    return tuple(rows)
