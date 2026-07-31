#!/usr/bin/env python3
"""Gera um arquivo `.xlsx`-shaped pequeno que descomprime para um `sharedStrings.xml` enorme —
o formato mais simples de zip bomb (uma string longa repetida comprime quase a zero). Use para
testar qualquer endpoint de upload que aceite `.xlsx`/zip: um limite de tamanho só no upload
comprimido não impede isto — o parsing pode alocar centenas de MB/gastar segundos de CPU a
partir de um arquivo de poucos KB.

Uso:
    python build_zip_bomb.py --output bomb.xlsx --target-mb 250
    # depois suba pelo endpoint de verdade e meça tempo/memória:
    curl -w "\\n%{time_total}s\\n" -F "file=@bomb.xlsx" http://localhost:8123/api/v1/imports/spreadsheet/stage \\
        -H "Cookie: <cookie de sessão>"

Um "PASS" é o endpoint rejeitar rápido (ex.: HTTP 422 em bem menos de 1s) com uma mensagem sobre
tamanho descomprimido — nunca travar segundos processando nem estourar memória do processo.
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>"""
_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>"""
_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Bomb" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
_SHEET = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData>
</worksheet>"""


def build(target_mb: int) -> bytes:
    huge_string = "A" * (target_mb * 1024 * 1024)
    shared_strings_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="1" uniqueCount="1"><si><t>{huge_string}</t></si></sst>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/workbook.xml", _WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        archive.writestr("xl/worksheets/sheet1.xml", _SHEET)
        archive.writestr("xl/sharedStrings.xml", shared_strings_xml)
    return buffer.getvalue()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--output", required=True, help="caminho do .xlsx a gerar")
    p.add_argument(
        "--target-mb",
        type=int,
        default=250,
        help="tamanho descomprimido alvo do sharedStrings.xml, em MB (padrão: 250)",
    )
    args = p.parse_args()

    content = build(args.target_mb)
    Path(args.output).write_bytes(content)

    print(f"Gerado: {args.output}")
    print(f"  tamanho no disco (comprimido): {len(content) / 1024:.1f} KB")
    print(f"  tamanho descomprimido do sharedStrings.xml: ~{args.target_mb} MB")
    print(
        "\nSuba este arquivo no endpoint de upload tocado e meça o tempo de resposta — deve ser "
        "rejeitado rápido, nunca processado por segundos nem derrubar o processo."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
