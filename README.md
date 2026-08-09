# Vertere Lab V2

Plataforma transacional do laboratório veterinário Vertere. O núcleo implementado cobre
identidade e acesso, cadastros estruturantes, Registro de Atendimento, fechamento por período,
ajustes financeiros e importações auditáveis.

## Requisitos

- Python 3.12 ou superior;
- [uv](https://docs.astral.sh/uv/);
- Node.js compatível com Vite 8 e npm;
- Docker, necessário para a suíte de integração com PostgreSQL real;
- PostgreSQL 17 para desenvolvimento local ou uma instância compatível.

## Instalação

```powershell
uv sync
cd frontend
npm ci
```

Não versione `.env`, credenciais, dumps ou dados reais. O backend exige `DATABASE_URL` e falha
imediatamente quando ela não está definida.

## Configuração

Variáveis principais do backend:

| Variável | Obrigatória | Uso |
|---|---:|---|
| `DATABASE_URL` | sim | URL `postgresql+psycopg://...` |
| `ENV` | não | `dev`, `test`, `staging` ou `prod` |
| `LOG_LEVEL` | não | nível de logging |
| `SESSION_COOKIE_SECURE` | produção | deve ser `true` sob HTTPS |
| `TRUSTED_BROWSER_ORIGINS` | produção | array JSON com as origens aceitas pelo controle CSRF |
| `SESSION_TTL_MINUTES` | não | duração da sessão comum |
| `SESSION_TTL_REMEMBER_ME_DAYS` | não | duração de “lembrar-me” |
| `VIACEP_BASE_URL` | não | endpoint da consulta de CEP |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` | não | limite de falhas de login |

O frontend usa `/api/v1` no mesmo origin por padrão. `VITE_API_BASE_URL` pode alterar a base em
builds específicos; cookies de sessão continuam sendo `HttpOnly` e nunca vão para
`localStorage`.

## Banco e migrations

Crie o banco e defina a URL antes de executar Alembic:

```powershell
$env:DATABASE_URL='postgresql+psycopg://vertere:vertere@localhost:5432/vertere'
uv run alembic heads
uv run alembic upgrade head
```

`alembic heads` deve retornar exatamente uma revisão. Para verificar rollback da última
migration em um banco descartável:

```powershell
uv run alembic downgrade -1
uv run alembic upgrade head
```

Nunca faça downgrade destrutivo em produção sem backup e plano de restauração.

## Execução local

Backend:

```powershell
uv run uvicorn --factory app.main:create_app --app-dir backend --reload --port 8000
```

Frontend, em outro terminal:

```powershell
cd frontend
npm run dev
```

O proxy de desenvolvimento encaminha `/api` ao backend configurado em
[`vite.config.ts`](frontend/vite.config.ts).

Para criar o primeiro administrador em um banco novo:

```powershell
cd backend
uv run python -m app.scripts.bootstrap_admin `
  --email admin@example.local `
  --full-name "Administrador" `
  --password "defina-uma-senha-forte"
```

## Validação

Backend completo:

```powershell
uv run ruff check backend
uv run ruff format --check backend
uv run mypy backend
uv run pytest -q
```

A integração usa Testcontainers e exige Docker ativo. O timeout da suíte não é aprovação.

Frontend completo:

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

Contratos OpenAPI:

```powershell
cd frontend
npm run api:generate
npm run api:check
```

`api:generate` exporta o schema FastAPI e regenera
[`generated.ts`](frontend/src/shared/api/generated.ts). O arquivo gerado não deve ser editado à
mão.

## Arquitetura

O backend segue domínio → aplicação → infraestrutura → API. Casos de uso dependem de protocolos
de repositório e Unit of Work; routers convertem HTTP e não controlam transações. PostgreSQL é a
fonte de verdade, com auditoria e outbox no mesmo commit das mutações críticas.

O frontend é organizado por feature. TanStack Query mantém estado remoto, React Hook Form/Zod
tratam formulários e o cliente HTTP compartilhado normaliza cookies e erros. Query keys incluem
o escopo do ator para impedir reaproveitamento de cache entre memberships.

```text
frontend -> FastAPI -> application/UoW -> PostgreSQL
                         | audit + outbox |
```

As decisões completas estão em [`docs/04-arquitetura.md`](docs/04-arquitetura.md) e
[`docs/adr/`](docs/adr/). O produto é definido por [`docs/02-prd.md`](docs/02-prd.md),
[`docs/03-modelo-de-dominio.md`](docs/03-modelo-de-dominio.md) e
[`docs/07-nucleo-v1.md`](docs/07-nucleo-v1.md).

## Limitações conhecidas

- `Owner` permanece embutido em `Patient`; permissões `owners.*` ainda não têm casos de uso.
- O preço vigente permanece diretamente em `Exam`, sem tabela versionada de preços.
- Alguns códigos de método de coleta preservam nomes históricos de pessoas.
- `MonthlyClosure` é o nome histórico de um fechamento que hoje aceita período livre.
- `PATCH /api/v1/users/{id}/role` é compatibilidade depreciada; clientes novos usam `/access`.
- O cenário Playwright integral contra backend real ainda precisa unir, em uma única jornada,
  cadastros, atendimento, fechamento, ajuste e tentativa cross-tenant.

Detalhes, impacto e estratégia de saída estão em
[`docs/08-divida-tecnica.md`](docs/08-divida-tecnica.md).
