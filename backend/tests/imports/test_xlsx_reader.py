from __future__ import annotations

import pytest

from app.modules.imports.infrastructure.xlsx_reader import InvalidXlsxError, read_workbook
from tests.imports.xlsx_builder import build_xlsx


def test_read_workbook_parses_sheet_name_cells_and_source_row_numbers() -> None:
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
    assert [row.row_number for row in sheet.rows] == [1, 2, 3]
    assert sheet.rows[0].cells == {"A": "Clínica", "B": "CNPJ", "C": "Status"}
    assert sheet.rows[1].cells == {
        "A": "Bicho Urbano",
        "B": "21.804.204/0001-55",
        "C": "Ativo",
    }
    # Célula vazia (None) fica ausente, não vira string vazia: o staging não inventa dado
    # que não estava no arquivo de origem.
    assert "B" not in sheet.rows[2].cells


def test_read_workbook_rejects_non_zip_content_and_decompression_bombs() -> None:
    with pytest.raises(InvalidXlsxError):
        read_workbook(b"not a zip file")

    # Regressão do QA: um upload de 192 KB (abaixo do teto de 20 MB comprimido do router)
    # descomprimia `sharedStrings.xml` para ~190 MB. Uma string longa repetida é a forma
    # clássica de zip bomb: comprime para quase nada.
    huge_cell = "A" * (210 * 1024 * 1024)  # acima do teto de 200 MB por parte
    with pytest.raises(InvalidXlsxError):
        read_workbook(build_xlsx("Bomb", [[huge_cell]]))
