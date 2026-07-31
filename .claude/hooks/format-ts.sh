#!/usr/bin/env bash
# PostToolUse: roda oxlint --fix em .ts/.tsx tocado pelo agente. Nunca bloqueia.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-.}"
f=$(python "$root/.claude/hooks/read-hook-json.py" tool_input.file_path)
[[ -z "$f" ]] && exit 0
[[ "$f" != *.ts && "$f" != *.tsx ]] && exit 0

cd "$root/frontend" 2>/dev/null || exit 0
npx oxlint --fix "$f" >/dev/null 2>&1 || true
exit 0