"""Hand-built minimal single-page PDF for tests — same spirit as
`xlsx_builder.py`: construct the real file format byte-for-byte instead of
depending on a PDF-writing library (there's no writer among the project's
existing dependencies, and adding one just to generate test fixtures isn't
worth it). Uses the standard, non-embedded Helvetica font and an
uncompressed content stream, with an exact byte-offset xref table computed
as the file is built.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class PdfTextItem:
    text: str
    x: float
    y: float
    size: float


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_price_table_pdf(items: list[PdfTextItem]) -> bytes:
    content_lines = []
    for item in items:
        content_lines.append("BT")
        content_lines.append(f"/F1 {item.size:g} Tf")
        content_lines.append(f"{item.x:g} {item.y:g} Td")
        content_lines.append(f"({_escape(item.text)}) Tj")
        content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
    ]

    buffer = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_offset = len(buffer)
    buffer += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    buffer += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        buffer += f"{offset:010d} 00000 n \n".encode("ascii")
    buffer += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode("ascii")

    return bytes(buffer)
