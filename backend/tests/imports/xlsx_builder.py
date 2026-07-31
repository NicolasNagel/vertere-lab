"""Builds a minimal in-memory `.xlsx` for tests — mirrors just enough of the
OOXML structure (shared strings + one or more worksheets) for `xlsx_reader`
to parse. No `openpyxl` dependency, same reasoning as the reader itself."""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape as xml_escape

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_COLUMN_LETTERS = [chr(ord("A") + i) for i in range(26)]


def _content_types_xml(sheet_count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, sheet_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
{overrides}
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>"""


def _workbook_rels_xml(sheet_count: int) -> str:
    sheet_rels = "".join(
        f'<Relationship Id="rId{i}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, sheet_count + 1)
    )
    shared_strings_rid = sheet_count + 1
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{sheet_rels}
<Relationship Id="rId{shared_strings_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>"""


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>'
        for i, name in enumerate(sheet_names, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>{sheets}</sheets>
</workbook>"""


def _shared_strings_xml(strings: list[str]) -> str:
    items = "".join(f"<si><t>{xml_escape(value)}</t></si>" for value in strings)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">
{items}
</sst>"""


def build_workbook(sheets: dict[str, list[list[str | None]]]) -> bytes:
    """`sheets` maps sheet name -> rows (each cell written as a shared
    string — good enough for staging tests, which never coerce types)."""
    strings: list[str] = []
    string_index: dict[str, int] = {}

    def _intern(value: str) -> int:
        if value not in string_index:
            string_index[value] = len(strings)
            strings.append(value)
        return string_index[value]

    def _sheet_xml(rows: list[list[str | None]]) -> str:
        row_xml_parts = []
        for row_number, row in enumerate(rows, start=1):
            cell_parts = []
            for col_index, value in enumerate(row):
                if value is None:
                    continue
                ref = f"{_COLUMN_LETTERS[col_index]}{row_number}"
                index = _intern(value)
                cell_parts.append(f'<c r="{ref}" t="s"><v>{index}</v></c>')
            row_xml_parts.append(f'<row r="{row_number}">{"".join(cell_parts)}</row>')
        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>{"".join(row_xml_parts)}</sheetData>
</worksheet>"""

    sheet_names = list(sheets.keys())
    sheet_xml_by_index = {i: _sheet_xml(rows) for i, rows in enumerate(sheets.values(), start=1)}

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheet_names)))
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/workbook.xml", _workbook_xml(sheet_names))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(len(sheet_names)))
        for i, sheet_xml in sheet_xml_by_index.items():
            archive.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml)
        archive.writestr("xl/sharedStrings.xml", _shared_strings_xml(strings))
    return buffer.getvalue()


def build_xlsx(sheet_name: str, rows: list[list[str | None]]) -> bytes:
    return build_workbook({sheet_name: rows})
