"""Parse the "Tabela de Preços" PDF into `(category, exam_name, price)` rows.

Unlike the `.xlsx` reader, this genuinely needs a library: plain top-to-bottom
text extraction (`pypdf.extract_text()`, tried first) interleaves the exam
names and their prices as two disconnected blocks, because the PDF's content
stream draws the price column and the label column as separate text runs —
reading order in the stream is not visual row order. `pdfplumber` (MIT
licensed, actively maintained) exposes per-word bounding boxes and font
sizes, which is what actually lets rows be reconstructed correctly. This was
verified against the real file (`assets/features/Tabela de Preços -
2026.pdf`) before writing this, not assumed:

- Category headers (`"perfis"`, `"Exames Hematológicos"`, `"Hemogasometria"`,
  ...) render at ~20pt; every item label/price renders at ~12pt/~8pt. Font
  size is a clean, reliable signal for "this row is a category header" —
  more reliable than "a row with no price", since some *item* rows also
  temporarily have no visible price (see multi-line labels below).
- Some exam names wrap across two physical lines before their price appears
  on a third (e.g. "Check-up 3"); those continuation lines carry no price
  and must be prepended onto the next row that does have one.
- Dot leaders between a label and its price sometimes merge into the same
  word token as the price (e.g. a token literally reading
  `"....................R$"`) when there's no whitespace between them in the
  source PDF — price extraction therefore has to be a regex over the row's
  full joined text, not a per-token split.
- A "Plantão" surcharge block (two lines, same two values, repeated
  identically on every page) is not an exam at all — it's a flat surcharge
  applied regardless of which exam was done. Deliberately excluded here: it
  doesn't belong on the exam catalog at all (the flat plantão fee now lives
  on `AttendanceRecord.on_call_fee`, keyed by `service_level`, not by exam —
  see `docs/01-analise-planilha.md` §6).
- At least one row ("Cálcio") had its price on the line *above* its label
  instead of below/same-line — the forward-only merge below can't recover
  that pairing; both halves surface as unpaired entries instead of being
  silently guessed at.

`_rows_from_words` is the actual row-reconstruction logic and takes plain
dicts (`top`, `x0`, `text`, `size`) — the same shape `pdfplumber.Page.
extract_words(extra_attrs=["size"])` returns — so it can be unit-tested
without a real PDF file. `read_price_table` is the thin wrapper that opens a
real PDF and calls it per page.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pdfplumber

# Shape of a `pdfplumber.Page.extract_words(extra_attrs=["size"])` entry — just the fields
# this module reads, not pdfplumber's full (untyped) word dict.
_Word = dict[str, str | float]

# A PDF's `/Length` on a compressed stream is the *compressed* size — unlike the xlsx reader's
# `ZipInfo.file_size`, there's no cheap metadata field for the decompressed size, so a
# decompression bomb can't be caught by reading a header. Confirmed by hand during QA: a 510KB
# hand-crafted PDF with one FlateDecode stream that inflates to 500MB made `pdfplumber.open()`
# hang the entire server for 2 minutes (blocking the async event loop, not just that request) —
# every other user's request timed out during that window. The fix mirrors the xlsx guard's
# actual intent (reject cheaply, never fully materialize the bomb) using incremental
# `zlib.decompressobj().decompress(data, max_length=...)`: it detects an oversized stream after
# producing at most this many bytes, never allocating the full inflated size.
_MAX_DECOMPRESSED_STREAM_SIZE = 50 * 1024 * 1024  # 50 MB — a real price table is a few KB of text
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)

_TITLE_FOLDED = "tabela de precos"
_HEADER_MIN_SIZE = 18.0
# Footnote text renders at ~10pt in the real file — a narrow band, not "<= 10.5", because a
# price-only row (no label on the same line, e.g. a wrapped multi-line name) renders its "R$
# nnn,nn" at ~8.2pt and must NOT be caught by this check. An earlier version used an open-ended
# "<= 10.5" cutoff, which silently dropped exactly this kind of row (caught by
# `test_multiline_label_is_merged_onto_the_row_that_finally_has_a_price` in
# `tests/imports/test_pdf_price_table_reader.py`) — bands for the sizes actually observed in the
# real PDF: ~4.5 dot leaders, ~8.2 price text, ~10.0 footnotes, ~12.0 item labels, ~20 headers.
_FOOTNOTE_MIN_SIZE = 9.5
_FOOTNOTE_MAX_SIZE = 11.0
_ROW_TOLERANCE = 4.0

_PRICE_RE = re.compile(r"R\s*\$\s*((?:\d\s*)+(?:[.,]\s*\d\s*\d)?)")
_DOTS_RE = re.compile(r"\.{2,}")


class InvalidPriceTablePdfError(ValueError):
    pass


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower().strip()


@dataclass(frozen=True, kw_only=True)
class PriceTableItem:
    page: int
    category: str
    name: str
    price: Decimal


@dataclass(frozen=True, kw_only=True)
class PriceTableParseResult:
    items: tuple[PriceTableItem, ...]
    ignored_surcharge_lines: tuple[str, ...]
    unpaired_lines: tuple[str, ...]


def _cluster_rows(words: list[_Word]) -> list[list[_Word]]:
    rows: list[list[_Word]] = []
    for word in sorted(words, key=lambda w: float(w["top"])):
        if rows and abs(float(rows[-1][0]["top"]) - float(word["top"])) <= _ROW_TOLERANCE:
            rows[-1].append(word)
        else:
            rows.append([word])
    return rows


def _rows_from_words(
    words: list[_Word], *, page_number: int
) -> tuple[list[PriceTableItem], list[str], list[str]]:
    items: list[PriceTableItem] = []
    ignored: list[str] = []
    unpaired: list[str] = []

    pending_label = ""
    current_category = ""

    for row in _cluster_rows(words):
        row_sorted = sorted(row, key=lambda w: float(w["x0"]))
        raw_text = " ".join(str(word["text"]) for word in row_sorted)
        max_size = max(float(word["size"]) for word in row_sorted)

        if _fold(raw_text) == _TITLE_FOLDED:
            continue
        if max_size >= _HEADER_MIN_SIZE:
            current_category = raw_text.strip()
            pending_label = ""
            continue
        if _FOOTNOTE_MIN_SIZE <= max_size <= _FOOTNOTE_MAX_SIZE:
            # Footnote line (e.g. "¹Testes que possuem dois doadores...") — never a
            # continuation of an item label, and shouldn't bleed into the next row.
            pending_label = ""
            continue

        price_match = _PRICE_RE.search(raw_text)
        label_part = _DOTS_RE.sub(" ", _PRICE_RE.sub("", raw_text)).strip()

        if _fold(label_part).startswith(("plantao", "plantoes")):
            ignored.append(raw_text.strip())
            pending_label = ""
            continue

        if price_match is None:
            if label_part:
                pending_label = f"{pending_label} {label_part}".strip()
            continue

        price_str = re.sub(r"\s+", "", price_match.group(1)).replace(",", ".")
        try:
            price = Decimal(price_str)
        except InvalidOperation:
            unpaired.append(f"página {page_number}: preço ilegível: {raw_text!r}")
            pending_label = ""
            continue

        name = f"{pending_label} {label_part}".strip()
        pending_label = ""
        if not name:
            unpaired.append(
                f"página {page_number}: preço sem nome de exame associado: {raw_text!r}"
            )
            continue

        items.append(
            PriceTableItem(page=page_number, category=current_category, name=name, price=price)
        )

    if pending_label:
        unpaired.append(
            f"página {page_number}: nome de exame sem preço associado: {pending_label!r}"
        )

    return items, ignored, unpaired


def _reject_if_decompression_bomb(content: bytes) -> None:
    for match in _STREAM_RE.finditer(content):
        raw = match.group(1)
        decompressor = zlib.decompressobj()
        produced = 0
        chunk = raw
        try:
            while chunk:
                output = decompressor.decompress(chunk, _MAX_DECOMPRESSED_STREAM_SIZE)
                produced += len(output)
                if produced > _MAX_DECOMPRESSED_STREAM_SIZE:
                    raise InvalidPriceTablePdfError(
                        "Arquivo PDF tem um stream cujo tamanho descomprimido excede o "
                        "máximo permitido."
                    )
                chunk = decompressor.unconsumed_tail
        except zlib.error:
            # Not a (valid) FlateDecode stream — could be a font/image binary blob or an
            # already-uncompressed stream; not this check's concern, and never a bomb since
            # nothing here was inflated.
            continue


def read_price_table(content: bytes) -> PriceTableParseResult:
    _reject_if_decompression_bomb(content)
    try:
        pdf = pdfplumber.open(io.BytesIO(content))
    except Exception as exc:  # pdfplumber/pypdfium2 raise assorted exceptions for bad input
        raise InvalidPriceTablePdfError(f"Arquivo PDF inválido ou corrompido: {exc}") from exc

    all_items: list[PriceTableItem] = []
    all_ignored: list[str] = []
    all_unpaired: list[str] = []
    try:
        for page_index, page in enumerate(pdf.pages):
            words = page.extract_words(extra_attrs=["size"])
            if not words:
                continue
            items, ignored, unpaired = _rows_from_words(words, page_number=page_index + 1)
            all_items.extend(items)
            all_ignored.extend(ignored)
            all_unpaired.extend(unpaired)
    finally:
        pdf.close()

    return PriceTableParseResult(
        items=tuple(all_items),
        ignored_surcharge_lines=tuple(all_ignored),
        unpaired_lines=tuple(all_unpaired),
    )
