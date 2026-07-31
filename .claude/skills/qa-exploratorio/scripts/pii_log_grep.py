#!/usr/bin/env python3
"""Varre um arquivo de log de verdade (o que o próprio backend gerou durante a sessão de QA)
atrás de PII em claro: CPF, CNPJ, e-mail, telefone brasileiro, e os literais
senha/token/cookie/connection string que nunca podem aparecer (`.claude/rules/06-auth-security-lgpd.md`
— "nunca aparece em log").

Uso:
    python pii_log_grep.py --log-file /tmp/scratch/uvicorn.log

Um "PASS" é zero ocorrências. Qualquer ocorrência é achado — mesmo que pareça inofensiva (e-mail
de teste ainda é o padrão que vazaria e-mail real em produção).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_PATTERNS: dict[str, re.Pattern[str]] = {
    "CPF (###.###.###-##)": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "CNPJ (##.###.###/####-##)": re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
    "e-mail": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "telefone BR ((##) #####-####)": re.compile(r"\(\d{2}\)\s?9?\s?\d{4}-?\d{4}"),
    "literal 'senha'/'password'": re.compile(r"(?i)\b(senha|password)\b\s*[:=]"),
    "literal 'token'": re.compile(r"(?i)\btoken\b\s*[:=]"),
    "literal 'cookie'": re.compile(r"(?i)\bcookie\b\s*[:=]"),
    "connection string (postgresql://...)": re.compile(r"postgres(?:ql)?://[^\s\"]+"),
}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--log-file", required=True)
    p.add_argument(
        "--allow-emails",
        action="store_true",
        help="não trata e-mail como achado (útil se o log só tem e-mails sintéticos de teste "
        "e você já validou isso manualmente linha a linha)",
    )
    args = p.parse_args()

    try:
        lines = (
            Path(args.log_file)
            .read_text(encoding="utf-8", errors="replace")
            .splitlines(keepends=True)
        )
    except OSError as e:
        print(f"Não consegui abrir {args.log_file}: {e}", file=sys.stderr)
        return 2

    patterns = dict(_PATTERNS)
    if args.allow_emails:
        patterns.pop("e-mail", None)

    findings: list[tuple[int, str, str]] = []
    for line_number, line in enumerate(lines, start=1):
        for label, pattern in patterns.items():
            match = pattern.search(line)
            if match:
                findings.append((line_number, label, match.group(0)))

    if not findings:
        print(f"PASS — nenhuma ocorrência em {len(lines)} linhas de {args.log_file}.")
        return 0

    print(f"FAIL — {len(findings)} ocorrência(s) em {args.log_file}:")
    for line_number, label, value in findings[:50]:
        print(f"  linha {line_number}: {label} -> {value!r}")
    if len(findings) > 50:
        print(f"  ... e mais {len(findings) - 50} ocorrência(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
