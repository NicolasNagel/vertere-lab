from __future__ import annotations

import zlib
from decimal import Decimal

import pytest

from app.modules.imports.infrastructure.pdf_price_table_reader import (
    InvalidPriceTablePdfError,
    _rows_from_words,
    read_price_table,
)


def _word(text: str, *, top: float, x0: float, size: float) -> dict[str, str | float]:
    return {"text": text, "top": top, "x0": x0, "size": size}


def _build_decompression_bomb_pdf() -> bytes:
    # Mirrors real QA: a single FlateDecode stream whose declared /Length is the *compressed*
    # size (small) but that inflates far past any real price table — the same class of bug the
    # xlsx reader's `_safe_read` already guards against, just without a cheap uncompressed-size
    # metadata field to check, since PDF's /Length is the on-disk (compressed) size.
    huge = b"0" * (200 * 1024 * 1024)
    compressed = zlib.compress(huge, 9)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(compressed)).encode("ascii")
        + b" /Filter /FlateDecode >>\nstream\n"
        + compressed
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


def test_read_price_table_rejects_decompression_bomb() -> None:
    bomb = _build_decompression_bomb_pdf()

    with pytest.raises(InvalidPriceTablePdfError):
        read_price_table(bomb)


def test_pairs_a_simple_name_and_price_on_the_same_row() -> None:
    words = [
        _word("Hemograma", top=100, x0=50, size=12),
        _word("R$", top=101, x0=490, size=8),
        _word("28,00", top=101, x0=510, size=8),
    ]

    items, ignored, unpaired = _rows_from_words(words, page_number=1)

    assert not ignored
    assert not unpaired
    assert len(items) == 1
    assert items[0].name == "Hemograma"
    assert items[0].price == Decimal("28.00")


def test_font_size_marks_a_row_as_a_category_header_not_an_item() -> None:
    words = [
        _word("Exames", top=50, x0=30, size=20),
        _word("Hematológicos", top=50, x0=100, size=20),
        _word("Hemograma", top=100, x0=50, size=12),
        _word("R$", top=101, x0=490, size=8),
        _word("28,00", top=101, x0=510, size=8),
    ]

    items, _, _ = _rows_from_words(words, page_number=1)

    assert len(items) == 1
    assert items[0].category == "Exames Hematológicos"


def test_multiline_label_is_merged_onto_the_row_that_finally_has_a_price() -> None:
    # Mirrors the real "Check-up 3" row: name wraps across two lines, price on a third.
    words = [
        _word("Check-up", top=200, x0=39, size=12),
        _word("3", top=200, x0=90, size=12),
        _word("(Hemograma,", top=200, x0=100, size=12),
        _word("Cai,", top=220, x0=39, size=12),
        _word("Cl,", top=220, x0=60, size=12),
        _word("P)", top=220, x0=90, size=12),
        _word("R$", top=240, x0=508, size=8),
        _word("140,00", top=240, x0=525, size=8),
    ]

    items, _, unpaired = _rows_from_words(words, page_number=1)

    assert not unpaired
    assert len(items) == 1
    assert items[0].name == "Check-up 3 (Hemograma, Cai, Cl, P)"
    assert items[0].price == Decimal("140.00")


def test_dot_leader_merged_into_the_price_token_is_still_parsed() -> None:
    # Mirrors a real row where the dot leader and "R$" ended up as one word token.
    words = [
        _word("Sódio", top=100, x0=40, size=12),
        _word("." * 80 + "R$", top=100, x0=90, size=12),
        _word("35,00", top=100, x0=528, size=8),
    ]

    items, _, _ = _rows_from_words(words, page_number=1)

    assert len(items) == 1
    assert items[0].name == "Sódio"
    assert items[0].price == Decimal("35.00")


def test_plantao_surcharge_lines_are_ignored_not_imported_as_exams() -> None:
    words = [
        _word("Plantão", top=100, x0=47, size=12),
        _word("R$", top=100, x0=499, size=8),
        _word("100,00", top=100, x0=517, size=8),
        _word("Plantões", top=120, x0=47, size=12),
        _word("de", top=120, x0=99, size=12),
        _word("domingo,", top=120, x0=116, size=12),
        _word("R$", top=120, x0=499, size=8),
        _word("150,00", top=120, x0=517, size=8),
    ]

    items, ignored, _ = _rows_from_words(words, page_number=1)

    assert items == []
    assert len(ignored) == 2


def test_footnote_row_is_dropped_and_does_not_bleed_into_the_next_item() -> None:
    words = [
        _word("¹Testes", top=560, x0=96, size=10),
        _word("que", top=560, x0=133, size=10),
        _word("possuem", top=560, x0=152, size=10),
        _word("dois", top=560, x0=197, size=10),
        _word("doadores.", top=560, x0=220, size=10),
        _word("Hemograma", top=600, x0=51, size=12),
        _word("R$", top=601, x0=496, size=8),
        _word("28,00", top=601, x0=513, size=8),
    ]

    items, _, unpaired = _rows_from_words(words, page_number=1)

    assert not unpaired
    assert len(items) == 1
    assert items[0].name == "Hemograma"


def test_price_with_no_preceding_label_becomes_unpaired_not_a_guess() -> None:
    # Mirrors the real "Cálcio" row where the price appeared on the line *above* the label —
    # the algorithm intentionally does not try to guess this pairing.
    words = [
        _word("R$", top=100, x0=491, size=8),
        _word("23,00", top=100, x0=508, size=8),
    ]

    items, _, unpaired = _rows_from_words(words, page_number=3)

    assert items == []
    assert len(unpaired) == 1
    assert "sem nome" in unpaired[0]


def test_trailing_label_with_no_price_at_end_of_page_becomes_unpaired() -> None:
    # A label-sized (12pt, not footnote-band) row with no price anywhere after it on the page —
    # e.g. a name whose price got cut off by a page break. Must never be silently dropped.
    words = [
        _word("Exame", top=700, x0=39, size=12),
        _word("Sem", top=700, x0=100, size=12),
        _word("Preço", top=700, x0=140, size=12),
    ]

    items, _, unpaired = _rows_from_words(words, page_number=1)

    assert items == []
    assert len(unpaired) == 1
    assert "sem preço" in unpaired[0]


def test_unparseable_price_becomes_unpaired_not_a_crash() -> None:
    words = [
        _word("Exame", top=100, x0=50, size=12),
        _word("Estranho", top=100, x0=100, size=12),
        _word("R$", top=100, x0=490, size=8),
        _word(",", top=100, x0=510, size=8),
    ]

    items, _, unpaired = _rows_from_words(words, page_number=1)

    assert items == []
    assert len(unpaired) == 1
