# Vertere Lab — Planejamento V2

Este pacote revisa o planejamento do sistema Vertere Lab para a stack definida e para a prioridade real da V1.

## Stack da V1

### Backend

- Python 3.12 ou superior;
- FastAPI;
- Pydantic v2 para contratos de entrada e saída;
- SQLAlchemy 2.x para persistência;
- Alembic para migrations;
- PostgreSQL como fonte de verdade;
- pytest para testes;
- Ruff para lint e formatação;
- mypy em modo estrito nos módulos de domínio e aplicação.

### Frontend

- React com TypeScript;
- Vite como build tool recomendado;
- React Router;
- TanStack Query para estado remoto;
- React Hook Form para formulários;
- Zod apenas no frontend para validação de experiência, sem substituir a validação Pydantic do backend;
- Playwright para testes E2E.

### Infraestrutura da V1

- frontend na Vercel;
- FastAPI na Vercel somente enquanto os fluxos forem HTTP curtos e stateless;
- PostgreSQL gerenciado com connection string de pooler;
- storage de objetos privado e compatível com S3 para laudos e anexos;
- Redis gerenciado apenas quando houver caso real para cache, rate limit, lock não transacional ou fila;
- tarefas persistentes e workers não devem depender do ciclo de vida de uma Function da Vercel.

## Prioridades absolutas

1. usuários, autenticação e permissões;
2. cadastros mestres necessários ao Registro de Atendimento;
3. Registro de Atendimento como agregado central;
4. fechamento mensal reproduzível e auditável;
5. migração e reconciliação da planilha;
6. somente após a estabilidade dessas bases: laudos, portal do cliente, coletas e comunicação 1:N.

## Decisão estrutural principal

O `AttendanceRecord` — Registro de Atendimento — é a espinha dorsal do sistema. Nenhum módulo que dependa dele pode inventar, duplicar ou corrigir seus dados fora dos casos de uso oficiais. O fechamento mensal consome snapshots financeiros dos atendimentos, e não recalcula o passado a partir de cadastros atuais.

## Documentos

1. `docs/01-analise-planilha.md` — diagnóstico da planilha atual;
2. `docs/02-prd.md` — produto e escopo revisado;
3. `docs/03-modelo-de-dominio.md` — entidades e invariantes;
4. `docs/04-arquitetura.md` — arquitetura Python/FastAPI/React/PostgreSQL/Vercel;
5. `docs/05-roadmap-backlog.md` — ordem de implementação da V1;
6. `docs/06-estrategia-qa.md` — estratégia de qualidade baseada em risco;
7. `docs/07-nucleo-v1.md` — especificação detalhada de usuários, permissões, atendimentos e fechamento;
8. `docs/adr/` — decisões arquiteturais registradas;
9. `AGENTS.md` — contrato central para agentes de IA;
10. `.claude/rules/*.md` — regras minuciosas por disciplina;
11. `docs/VERTERE_LAB_PLANO_COMPLETO.md` — consolidação de todos os documentos.
