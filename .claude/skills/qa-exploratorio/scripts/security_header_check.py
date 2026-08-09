#!/usr/bin/env python3
"""Checa cabeçalhos de segurança HTTP de verdade, contra uma URL real (backend ou frontend).

Uso:
    python security_header_check.py --url http://localhost:8000/api/v1/attendances

Não é exaustivo nem substitui um scanner dedicado — é uma checagem barata que pega omissão óbvia
antes de virar hábito de "esquecer o header em todo endpoint novo".
"""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    print("Requer httpx: pip install httpx.", file=sys.stderr)
    raise SystemExit(2) from None

# Cada entrada: (header, o que checar). Checagem simples de presença/valor plausível — não
# valida a política inteira, só a ausência total, que é o erro mais comum.
CHECAGENS = [
    ("X-Content-Type-Options", lambda v: v == "nosniff"),
    ("Content-Security-Policy", lambda v: v is not None),
    ("Cache-Control", lambda v: v is not None),  # sensível a resposta com dado de paciente/preço
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", required=True)
    p.add_argument(
        "--require-hsts",
        action="store_true",
        help="exige HSTS mesmo ao testar um endpoint HTTP local configurado como produção",
    )
    p.add_argument(
        "--header",
        action="append",
        default=[],
        help="header adicional para enviar, formato Nome:Valor (ex.: Authorization:Bearer x)",
    )
    args = p.parse_args()

    headers = {}
    for h in args.header:
        if ":" not in h:
            print(f"Ignorando header mal formatado: {h}", file=sys.stderr)
            continue
        k, v = h.split(":", 1)
        headers[k.strip()] = v.strip()

    try:
        resp = httpx.get(args.url, headers=headers, timeout=10, follow_redirects=True)
    except httpx.HTTPError as e:
        print(f"ERRO DE REDE — não foi possível testar: {e}", file=sys.stderr)
        return 2

    print(f"GET {args.url} -> {resp.status_code}\n")
    checks = list(CHECAGENS)
    if args.require_hsts or urlparse(args.url).scheme == "https":
        checks.insert(0, ("Strict-Transport-Security", lambda v: v is not None))
    else:
        print(
            "  Strict-Transport-Security: não exigido em HTTP local; "
            "use --require-hsts para validar a configuração de produção"
        )

    faltando = []
    for nome, validador in checks:
        valor = resp.headers.get(nome)
        ok = validador(valor)
        status = "OK" if ok else "FALTANDO/INVÁLIDO"
        print(f"  {nome}: {valor!r} — {status}")
        if not ok:
            faltando.append(nome)

    # HTTPS não é testável contra localhost — sinalize isso em vez de fingir que checou.
    if (
        args.url.startswith("http://")
        and "localhost" not in args.url
        and "127.0.0.1" not in args.url
    ):
        print(
            "\nATENÇÃO: URL não é HTTPS e não é localhost — checagem de TLS não realizada "
            "por este script; confirme manualmente em produção/staging."
        )

    if faltando:
        print(f"\n{len(faltando)} header(s) ausente(s) ou inválido(s): {faltando}")
        return 1
    print("\nTodos os headers checados estão presentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
