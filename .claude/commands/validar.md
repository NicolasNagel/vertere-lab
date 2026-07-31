---
description: Gate rápido de validação — ruff + mypy + pytest (+ lint/tsc/test do frontend se tocado). Rode antes de cada commit.
---
# /validar — gate rápido
Rode o gate de validação do time e **conserte até passar**. O hook de `Stop` executa apenas o
subconjunto rápido de Ruff, format e mypy; pytest, frontend e migrações dependem deste comando
explícito antes de commitar uma fatia.

## Backend (sempre)
```bash
uv run ruff check backend && uv run ruff format --check backend && uv run mypy backend && uv run pytest -q
```
- Se **ruff** acusar: deixe o autofix resolver o que dá e corrija o resto à mão.
- Se **mypy** acusar: conserte a tipagem; não silencie com `# type: ignore` sem justificar.
- Se **pytest** falhar: conserte o código (não o teste, salvo se o teste estiver errado).

## Migração (se o diff tocou `models.py` ou `alembic/`)
```bash
uv run alembic upgrade head
```
Schema mudou sem migração no diff = vermelho. Migração que não sobe do zero = vermelho.

## Frontend (se o diff tocou `frontend/`)
```bash
cd frontend && npm run lint && npm run typecheck && npm run test && npm run build
```
- Erro de tipo não se resolve com `as any` — conserte o tipo ou o schema Zod de origem.

Só considere a tarefa pronta quando o gate sair **verde**. Não comite vermelho.
