#!/usr/bin/env bash
# PostToolUse: roda oxlint --fix em .ts/.tsx tocado pelo agente. Nunca bloqueia.
set -uo pipefail

f=$(jq -r '.tool_input.file_path // empty')
[[ -z "$f" ]] && exit 0
[[ "$f" != *.ts && "$f" != *.tsx ]] && exit 0

cd "${CLAUDE_PROJECT_DIR:-.}/frontend" 2>/dev/null || exit 0
npx oxlint --fix "$f" >/dev/null 2>&1 || true
exit 0