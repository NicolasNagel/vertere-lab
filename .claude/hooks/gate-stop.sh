#!/usr/bin/env bash
# Stop: impede o agente de encerrar o turno com lint/tipagem quebrada no backend.
# exit 2 = bloqueia e devolve o stderr ao agente para consertar.
# pytest fica de fora por custo — roda no /validar e no CI.
set -uo pipefail

input=$(cat)
[[ $(echo "$input" | jq -r '.stop_hook_active // false') == "true" ]] && exit 0

cd "${CLAUDE_PROJECT_DIR:-.}/backend" 2>/dev/null || exit 0

out=$(uv run ruff check . 2>&1) || {
  printf 'Gate vermelho (ruff). Conserte antes de encerrar:\n%s\n' "$out" >&2
  exit 2
}
out=$(uv run mypy . 2>&1) || {
  printf 'Gate vermelho (mypy). Conserte antes de encerrar:\n%s\n' "$out" >&2
  exit 2
}
exit 0