#!/usr/bin/env bash
# Stop: impede o agente de encerrar o turno com lint/tipagem quebrada no backend.
# exit 2 = bloqueia e devolve o stderr ao agente para consertar.
# pytest fica de fora por custo — roda no /validar e no CI.
set -uo pipefail

input=$(cat)
[[ $(echo "$input" | jq -r '.stop_hook_active // false') == "true" ]] && exit 0

# Mesmos comandos do /validar, sempre a partir da raiz (config de ruff/mypy no
# pyproject.toml raiz — mypy não descobre config a partir de subdiretório).
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
[[ -d backend ]] || exit 0

out=$(uv run ruff check backend 2>&1) || {
  printf 'Gate vermelho (ruff). Conserte antes de encerrar:\n%s\n' "$out" >&2
  exit 2
}
out=$(uv run mypy backend 2>&1) || {
  printf 'Gate vermelho (mypy). Conserte antes de encerrar:\n%s\n' "$out" >&2
  exit 2
}
exit 0