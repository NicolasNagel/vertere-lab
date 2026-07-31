#!/usr/bin/env bash
# PostToolUse: formata todo .py tocado pelo agente. Nunca bloqueia (exit 0 sempre) —
# o gate duro fica no hook Stop.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-.}"
f=$(python "$root/.claude/hooks/read-hook-json.py" tool_input.file_path)
[[ -z "$f" || "$f" != *.py ]] && exit 0

cd "$root" 2>/dev/null || exit 0
uv run ruff format "$f" >/dev/null 2>&1 || true
uv run ruff check --fix "$f" >/dev/null 2>&1 || true
exit 0