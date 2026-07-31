#!/usr/bin/env python3
"""Testa mass assignment de verdade: envia um payload normal + um campo extra que o cliente não
deveria poder controlar (ex.: `role`, `clinic_id`, `status`, `grand_total`, `is_admin`) e confirma
que o backend ignora ou rejeita o campo — nunca que ele "pegou".

Com `extra='forbid'` (rule do projeto para entrada sensível), o esperado é a request inteira
falhar com 422 por causa do campo desconhecido — isso também é PASS, não só "salvou sem o campo".

Uso:
    python mass_assignment_probe.py \\
        --base-url http://localhost:8123 --method POST --path /api/v1/clinics \\
        --email admin@qa.local --password "S3nhaForteQA!" \\
        --json '{"name": "Clínica MA Test", "status": "ACTIVE"}' \\
        --extra-field role=SUPER_ADMIN
"""

from __future__ import annotations

import argparse
import json
import sys

try:
    import httpx
except ImportError:
    print("Requer httpx: pip install httpx (ou uv add --dev httpx no backend).", file=sys.stderr)
    raise SystemExit(2) from None


def _parse_extra(pairs: list[str]) -> dict[str, object]:
    extra: dict[str, object] = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"Ignorando --extra-field mal formatado: {pair}", file=sys.stderr)
            continue
        key, raw_value = pair.split("=", 1)
        try:
            value: object = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        extra[key.strip()] = value
    return extra


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--base-url", required=True)
    p.add_argument("--method", default="POST")
    p.add_argument("--path", required=True)
    p.add_argument("--login-url", default="/api/v1/auth/login")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--json", required=True, help="corpo JSON legítimo, sem o campo extra")
    p.add_argument(
        "--extra-field",
        action="append",
        default=[],
        required=True,
        help="campo=valor a injetar (repetível); valor é JSON quando possível, senão string",
    )
    args = p.parse_args()

    body: dict[str, object] = json.loads(args.json)
    extra = _parse_extra(args.extra_field)
    poisoned_body = {**body, **extra}

    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        login_resp = client.post(
            args.login_url,
            json={"login": args.email, "password": args.password, "remember_me": False},
        )
        if login_resp.status_code != 200:
            print(
                f"Login falhou ({login_resp.status_code}): {login_resp.text[:300]}", file=sys.stderr
            )
            return 2

        print(f"{args.method} {args.path} com campo(s) extra {extra} ...")
        resp = client.request(args.method, args.path, json=poisoned_body)

    print(f"Status: {resp.status_code}")
    print(f"Corpo: {resp.text[:500]}")

    if resp.status_code in (422, 400):
        print(
            "PASS — request rejeitada por causa do campo desconhecido (extra='forbid' ou validação)."
        )
        return 0

    if resp.status_code in (200, 201):
        try:
            response_body = resp.json()
        except ValueError:
            print("INCONCLUSIVO — resposta 2xx sem JSON parseável; confira manualmente.")
            return 3
        leaked = {k: v for k, v in extra.items() if response_body.get(k) == v}
        if leaked:
            print(f"FAIL — o(s) campo(s) extra apareceu(ram) refletido(s) na resposta: {leaked}")
            return 1
        print(
            "PASS — request aceita, mas o(s) campo(s) extra não aparece(m) na resposta com o "
            "valor injetado. Confirme manualmente no banco que o efeito também não ocorreu "
            "(ex.: papel do usuário, clínica dona do recurso)."
        )
        return 0

    print(f"INCONCLUSIVO — status inesperado ({resp.status_code}), verifique manualmente.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
