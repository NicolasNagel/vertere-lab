#!/usr/bin/env python3
"""Testa concorrência real de verdade: dispara N chamadas quase simultâneas (`asyncio.gather`,
nunca sequencial fingindo concorrência) contra o mesmo endpoint/recurso e reporta o que cada
uma respondeu. Não sabe olhar o banco por você — depois de rodar isto, confira a contagem real
(`SELECT COUNT(*), COUNT(DISTINCT <coluna-chave>) FROM <tabela>`) para saber se duplicou.

Um payload pequeno pode não abrir a janela de corrida — se nada suspeito aparecer na primeira
tentativa, rode de novo com um corpo maior (`--json-file` apontando pra um payload com mais
linhas/itens) antes de concluir que está seguro.

Uso (sessão por cookie — login real):
    python concurrency_probe.py \\
        --base-url http://localhost:8123 \\
        --method POST --path /api/v1/imports/<batch_id>/clinics \\
        --email admin@qa.local --password "S3nhaForteQA!" \\
        --requests 8

Uso com corpo JSON (ex.: criar o mesmo recurso em paralelo):
    python concurrency_probe.py \\
        --base-url http://localhost:8123 \\
        --method POST --path /api/v1/clinics \\
        --email admin@qa.local --password "S3nhaForteQA!" \\
        --json '{"name": "Clínica Concorrente", "status": "ACTIVE"}' \\
        --requests 6
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Requer httpx: pip install httpx (ou uv add --dev httpx no backend).", file=sys.stderr)
    raise SystemExit(2) from None


async def _run(
    *,
    base_url: str,
    method: str,
    path: str,
    email: str,
    password: str,
    login_url: str,
    body: dict[str, object] | None,
    requests: int,
) -> int:
    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        login_resp = await client.post(
            login_url, json={"login": email, "password": password, "remember_me": False}
        )
        if login_resp.status_code != 200:
            print(
                f"Login falhou ({login_resp.status_code}): {login_resp.text[:300]}", file=sys.stderr
            )
            return 2
        print(
            f"Login OK como {email}. Disparando {requests} chamadas concorrentes em {method} {path}..."
        )

        async def _call() -> httpx.Response:
            return await client.request(method, path, json=body)

        responses = await asyncio.gather(*[_call() for _ in range(requests)])

    status_counts = Counter(r.status_code for r in responses)
    print(f"\nStatus codes: {dict(status_counts)}")

    for i, r in enumerate(responses):
        snippet = r.text[:200].replace("\n", " ")
        print(f"  [{i}] {r.status_code} {snippet}")

    print(
        "\nISTO NÃO CONFIRMA AUSÊNCIA DE DUPLICAÇÃO SOZINHO — confira agora o banco de dados: "
        "SELECT COUNT(*), COUNT(DISTINCT <coluna-chave>) FROM <tabela> WHERE <condição do teste>; "
        "as duas contagens devem bater."
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--base-url", required=True)
    p.add_argument("--method", default="POST")
    p.add_argument("--path", required=True, help="path completo, ex.: /api/v1/imports/<id>/clinics")
    p.add_argument("--login-url", default="/api/v1/auth/login")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--json", help="corpo JSON literal para cada chamada")
    p.add_argument(
        "--json-file", help="arquivo com corpo JSON para cada chamada (alternativa a --json)"
    )
    p.add_argument("--requests", type=int, default=8, help="quantas chamadas concorrentes disparar")
    args = p.parse_args()

    body: dict[str, object] | None = None
    if args.json_file:
        body = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    elif args.json:
        body = json.loads(args.json)

    return asyncio.run(
        _run(
            base_url=args.base_url,
            method=args.method,
            path=args.path,
            email=args.email,
            password=args.password,
            login_url=args.login_url,
            body=body,
            requests=args.requests,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
