#!/usr/bin/env python3
"""Testa IDOR/BOLA de verdade: tenta acessar um recurso da clínica A usando a sessão de um
usuário da clínica B. Uso real contra API rodando — não é um mock, é uma chamada HTTP de verdade.

Este projeto usa **sessão opaca por cookie** (`docs/adr/001-autenticacao-sessao-opaca-argon2.md`),
não Bearer token — por isso o modo padrão faz login de verdade e reaproveita o cookie que o
próprio backend emite. Use `--email`/`--password` (o caso comum aqui). `--token-b` continua
disponível para quando o alvo testado usa Bearer token (outro projeto, outro serviço).

Uso (sessão por cookie — caso comum neste projeto):
    python probe_idor.py \\
        --base-url http://localhost:8000 \\
        --resource /api/v1/attendances/{id} \\
        --resource-id-a <id de um recurso criado pela clínica A> \\
        --login-url /api/v1/auth/login \\
        --email usuario-clinica-b@exemplo.com --password "senha-de-teste"

Uso (Bearer token — outros backends):
    python probe_idor.py \\
        --base-url http://localhost:8000 \\
        --resource /api/v1/attendances/{id} \\
        --resource-id-a <id de um recurso criado pela clínica A> \\
        --token-b <token de um usuário da clínica B>

Saída: PASS (bloqueou corretamente, 403/404) ou FAIL (vazou dado — 200 com corpo de outra
clínica). Sempre roda contra dado sintético (`app/scripts/bootstrap_admin.py` + usuários de
teste criados na mesma sessão) — nunca contra produção.
"""

from __future__ import annotations

import argparse
import sys

try:
    import httpx
except ImportError:
    print("Requer httpx: pip install httpx (ou uv add --dev httpx no backend).", file=sys.stderr)
    raise SystemExit(2) from None


def _login_client(base_url: str, login_url: str, email: str, password: str) -> httpx.Client:
    client = httpx.Client(base_url=base_url, timeout=10)
    resp = client.post(login_url, json={"login": email, "password": password, "remember_me": False})
    if resp.status_code != 200:
        print(f"Login falhou ({resp.status_code}) para {email}: {resp.text[:300]}", file=sys.stderr)
        raise SystemExit(2)
    return client


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--base-url", required=True)
    p.add_argument("--resource", required=True, help="path com {id}, ex.: /api/v1/attendances/{id}")
    p.add_argument(
        "--resource-id-a", required=True, help="ID de um recurso pertencente à clínica A"
    )

    p.add_argument("--login-url", default="/api/v1/auth/login")
    p.add_argument("--email", help="e-mail do usuário da clínica B (modo sessão por cookie)")
    p.add_argument("--password", help="senha do usuário da clínica B (modo sessão por cookie)")

    p.add_argument("--token-b", help="Bearer token de um usuário da clínica B (modo header)")
    p.add_argument("--auth-header", default="Authorization")
    p.add_argument("--auth-scheme", default="Bearer")
    args = p.parse_args()

    if not args.token_b and not (args.email and args.password):
        p.error("informe --email/--password (sessão por cookie) ou --token-b (Bearer)")

    path = args.resource.format(id=args.resource_id_a)

    if args.email and args.password:
        client = _login_client(args.base_url, args.login_url, args.email, args.password)
        print(f"Login OK como {args.email} (sessão por cookie).")
        request = lambda: client.get(path)  # noqa: E731
    else:
        headers = {args.auth_header: f"{args.auth_scheme} {args.token_b}".strip()}
        client = httpx.Client(base_url=args.base_url, timeout=10)
        request = lambda: client.get(path, headers=headers)  # noqa: E731

    print(f"GET {args.base_url.rstrip('/')}{path}\n  tentando acessar recurso da clínica A...")
    try:
        resp = request()
    except httpx.HTTPError as e:
        print(f"ERRO DE REDE — não foi possível testar: {e}", file=sys.stderr)
        return 2
    finally:
        client.close()

    print(f"Status: {resp.status_code}")

    if resp.status_code in (403, 404):
        print("PASS — acesso negado corretamente.")
        return 0

    if resp.status_code == 200:
        print(
            "FAIL — conseguiu ler um recurso de outra clínica. Corpo da resposta "
            "(inspecione se há dado de outro tenant vazando):"
        )
        print(resp.text[:1000])
        return 1

    print(f"INCONCLUSIVO — status inesperado ({resp.status_code}), verifique manualmente.")
    print(resp.text[:500])
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
