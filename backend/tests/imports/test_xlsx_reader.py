from __future__ import annotations

import pytest

from app.modules.imports.infrastructure.xlsx_reader import InvalidXlsxError, read_workbook
from tests.imports.xlsx_builder import build_xlsx


def test_read_workbook_parses_sheet_name_and_rows() -> None:
    content = build_xlsx(
        "Cadastro Clínicas",
        [
            ["Clínica", "CNPJ", "Status"],
            ["Bicho Urbano", "21.804.204/0001-55", "Ativo"],
            ["Schweitzer", None, "Ativo"],
        ],
    )

    sheets = read_workbook(content)

    assert len(sheets) == 1
    sheet = sheets[0]
    assert sheet.name == "Cadastro Clínicas"
    assert len(sheet.rows) == 3
    assert sheet.rows[0].cells == {"A": "Clínica", "B": "CNPJ", "C": "Status"}
    assert sheet.rows[1].cells == {
        "A": "Bicho Urbano",
        "B": "21.804.204/0001-55",
        "C": "Ativo",
    }
    # A skipped cell (None) is simply absent, not written as an empty string —
    # staging must not invent data that was not in the source file.
    assert "B" not in sheet.rows[2].cells


def test_read_workbook_preserves_source_row_numbers() -> None:
    content = build_xlsx("Dados", [["a"], ["b"], ["c"]])

    sheets = read_workbook(content)

    assert [row.row_number for row in sheets[0].rows] == [1, 2, 3]


def test_read_workbook_rejects_non_zip_content() -> None:
    with pytest.raises(InvalidXlsxError):
        read_workbook(b"not a zip file")


def test_read_workbook_rejects_decompression_bomb() -> None:
    # Regression found via QA against a running instance: a 192 KB upload
    # (well under the router's 20 MB compressed-size cap) decompressed a
    # `sharedStrings.xml` to ~190 MB — the compressed-size check never sees
    # that, since it only bounds what crosses the wire. One long repeated
    # string is the classic zip-bomb shape: it compresses to almost nothing.
    huge_cell = "A" * (210 * 1024 * 1024)  # over the 200 MB part-size cap
    content = build_xlsx("Bomb", [[huge_cell]])

    with pytest.raises(InvalidXlsxError):
        read_workbook(content)
