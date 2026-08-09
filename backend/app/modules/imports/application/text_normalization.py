"""Shared name-normalization helpers for matching free-text spreadsheet
names back to already-imported catalog entries — same deterministic
accent/case/punctuation folding everywhere a name needs to resolve to an
existing `Exam`, never a probabilistic/fuzzy match
(`.claude/rules/10-data-migration.md`: "nenhum merge incerto automático").

Extracted from `import_exams_from_history.py`/`import_price_table.py` (each
had its own copy) so every phase that resolves an exam name — including
Fase 4's combined-line ("Check-up 2 + Urinálise") component split — folds
punctuation the exact same way the catalog's own `code` was derived, instead
of drifting into three subtly different definitions of "the same name".
"""

from __future__ import annotations

import re
import unicodedata

_OWNER_SUFFIX_PATTERN = re.compile(r"^(?P<name>.*?)\s*\((?P<code>[^()]*)\)\s*$")


def fold_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def merge_key(name: str) -> str:
    """Case+accent-folded key — used to merge spelling variants of the same
    name (`"Hemograma"` vs `"hemograma"`) before deciding they're the same
    entity."""
    return fold_accents(name).lower()


def derive_exam_code(name: str) -> str:
    """Same fold as `merge_key`, plus stripping every non-alphanumeric
    character — this is how `Exam.code` itself was derived when the catalog
    entry was first created from history, so it doubles as a punctuation-
    insensitive lookup key (`"Check-up 2"` / `"Check up 2"` / `"Check-up  2"`
    all derive to `"CHECKUP2"`)."""
    return "".join(char for char in fold_accents(name).upper() if char.isalnum())


def split_owner_name(raw: str) -> str:
    """Strips a trailing `"(code)"`/`"(NI)"` suffix from a `Dados`-sheet
    "Proprietário" cell, keeping only the owner name — the same name a
    `Patient` was created/looked-up with (`import_patients.py`). Shared so
    Fase 4's attendance-history import resolves a row's owner text to the
    *exact* same string `get_by_owner_and_name` was originally called with,
    never a slightly different extraction that would miss the patient."""
    match = _OWNER_SUFFIX_PATTERN.match(raw)
    if match is None:
        return raw.strip()
    return match.group("name").strip() or raw.strip()
