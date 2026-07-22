#!/usr/bin/env bash
# PostToolUse: formata todo .py tocado pelo agente. Nunca bloqueia (exit 0 sempre) —
# o gate duro fica no hook Stop.
set -uo pipefail

f=$(jq -r '.tool_input.file_path // empty')
[[ -z "$f" || "$f" != *.py ]] && exit 0

cd "${CLAUDE_PROJECT_DIR:-.}/backend" 2>/dev/null || cd "${CLAUDE_PROJECT_DIR:-.}"
uv run ruff format "$f" >/dev/null 2>&1 || true
uv run ruff check --fix "$f" >/dev/null 2>&1 || true
exit 0