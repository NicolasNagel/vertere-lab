#!/usr/bin/env python3
"""Testa rate limit/bloqueio de força bruta de verdade: dispara N tentativas de login inválidas
seguidas contra o endpoint de login e reporta se em algum ponto o backend passou a responder
diferente (429, mensagem de bloqueio, atraso crescente) — versus continuar respondendo 401 pra
sempre, que é a ausência de proteção.

Uso:
    python brute_force_probe.py \\
        --base-url http://localhost:8123 --login-url /api/v1/auth/login \\
        --email vitima@qa.local --attempts 20
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

try:
    import httpx
except ImportError:
    print("Requer httpx: pip install httpx (ou uv add --dev httpx no backend).", file=sys.stderr)
    raise SystemExit(2) from None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--base-url", required=True)
    p.add_argument("--login-url", default="/api/v1/auth/login")
    p.add_argument("--email", required=True, help="e-mail de um usuário de teste existente")
    p.add_argument("--attempts", type=int, default=20)
    args = p.parse_args()

    statuses: list[int] = []
    durations: list[float] = []
    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        for i in range(args.attempts):
            start = time.monotonic()
            resp = client.post(
                args.login_url,
                json={"login": args.email, "password": f"senha-errada-{i}", "remember_me": False},
            )
            elapsed = time.monotonic() - start
            statuses.append(resp.status_code)
            durations.append(elapsed)
            print(f"  tentativa {i + 1:3d}: {resp.status_code} em {elapsed:.2f}s")

    counts = Counter(statuses)
    print(f"\nStatus codes: {dict(counts)}")
    # Só 429/423 contam como bloqueio. Antes, qualquer status diferente de 401/400 (um 404 de URL
    # errada, um 500) virava PASS — falso positivo que escondeu um login-url mal passado.
    if not any(code in (401, 400, 429, 423) for code in statuses):
        print(
            f"INVÁLIDO — o endpoint nunca respondeu como login ({dict(Counter(statuses))}). "
            "Confira --base-url/--login-url (no Git Bash use MSYS_NO_PATHCONV=1)."
        )
        return 2
    blocked_seen = any(code in (429, 423) for code in statuses)
    growing_delay = durations[-1] > durations[0] * 3 and durations[-1] > 1.0

    if blocked_seen:
        print(
            "PASS — backend passou a bloquear/responder diferente antes de esgotar as tentativas."
        )
        return 0
    if growing_delay:
        print(
            "PASS (parcial) — sem status de bloqueio explícito, mas o tempo de resposta cresceu "
            f"de {durations[0]:.2f}s para {durations[-1]:.2f}s (possível atraso progressivo). "
            "Confirme manualmente se isso é throttling intencional."
        )
        return 0

    print(
        f"FAIL — {args.attempts} tentativas seguidas, todas respondendo igual "
        f"({dict(counts)}), sem sinal de rate limit/bloqueio."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
