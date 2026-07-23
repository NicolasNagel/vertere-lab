# Vertere Lab V2 · guia do agente
> Responde: "o que vale para o projeto inteiro?" — carregado em toda sessão. Índice de fatos
> duráveis, não documentação. Regras por área ficam em `.claude/rules/`. Fonte de verdade do
> produto: `docs/02-prd.md`, `docs/03-modelo-de-dominio.md`, `docs/07-nucleo-v1.md`.

## Missão
Substituir a planilha operacional por uma plataforma transacional íntegra, auditável e
escalável. **`AttendanceRecord` (Registro de Atendimento) e o fechamento mensal são o núcleo** —
nada mais é considerado estável enquanto identidade, permissões, cadastros estruturantes,
atendimento e fechamento não estiverem corretos (docs/02-prd.md §1).

## Stack
Backend **FastAPI** (Python 3.12+) + **Pydantic v2** + **SQLAlchemy 2.x** + **Alembic** +
**PostgreSQL** (fonte de verdade única). Frontend **React + TypeScript** (Vite, React Router,
TanStack Query, React Hook Form, Zod só para validação de experiência — Pydantic no backend é
quem decide). Infra: **Vercel** para frontend e, enquanto os fluxos forem HTTP curtos e
stateless, para o backend também; **Redis é opcional**, só entra com justificativa medida
(cache, rate limit, lock não-transacional, fila com worker externo) — nunca como fonte de
verdade. Não trocar peça estrutural da stack sem ADR em `docs/adr/`.

## Ordem de leitura ao pegar uma tarefa
1. este arquivo;
2. `.claude/rules/globals.md` + `.claude/rules/product-domain.md` (sempre carregados);
3. a rule técnica da área tocada (`paths:` já filtra isso automaticamente);
4. `.claude/rules/attendance.md` se a tarefa tocar cadastro/atendimento, ou
   `.claude/rules/monthly-closure.md` se tocar financeiro;
5. PRD, modelo de domínio e ADRs afetados em `docs/`.

## Prioridade de implementação (não inverter)
1. autenticação, usuários, papéis e permissões;
2. cadastros estruturantes (clínicas, veterinários, proprietários, pacientes, catálogo, preços);
3. Registro de Atendimento;
4. fechamento mensal;
5. migração da planilha;
6. só depois: resultados, laudos, portal, coletas, comunicação 1:N.
É proibido priorizar módulo P1/P2 criando atalho que comprometa essa ordem (`docs/05-roadmap-backlog.md` §12 — "ordem proibida").

## Decisões não negociáveis
- **PostgreSQL é a única fonte de verdade** — Redis nunca guarda atendimento, preço, fechamento,
  permissão ou laudo.
- **Autorização só no backend**, sempre considerando escopo (laboratório ou clínica). Papel
  agrupa permissão; código nunca decide por nome de papel, só por `resource.action`.
- **`AttendanceRecord` é a raiz do agregado operacional** — todo módulo futuro referencia por ID
  e respeita seus snapshots; nunca duplica dado de atendimento em módulo paralelo.
- **Dinheiro é `Decimal`/`NUMERIC`, nunca `float`.** Total é calculado no servidor.
- **Preço do atendimento é snapshot imutável** — reajuste de tabela não altera atendimento já
  confirmado.
- **Fechamento fechado é imutável.** Correção depois disso é ajuste (append-only) ou reabertura
  auditada — nunca edição direta.
- **Protocolo é gerado transacionalmente** (lock + constraint única) — `SELECT MAX + 1` é
  proibido, é a causa raiz do problema que estamos resolvendo (`docs/01-analise-planilha.md` §2.7).
- **Criação de atendimento e fechamento são idempotentes** via `Idempotency-Key`.
- **Serviço externo nunca participa da transação de negócio** (e-mail, PDF, storage — sempre
  fora do commit crítico, via outbox).
- **`audit_log` append-only em toda ação crítica** (login, papel, cadastro mestre, atendimento,
  override de preço, fechamento, ajuste, reabertura, importação).
- **Vercel é stateless**: nada de worker persistente, scheduler ou estado em memória entre
  requisições — ver `.claude/rules/redis-queues.md` para os gatilhos de sair da Vercel.
- **Segredo e PII nunca em código ou log.**

## Onde fica o quê
- regras por área (path-scoped via `paths:`, carregam só ao tocar a área): `.claude/rules/`
- subagentes (verificação *soft*): `.claude/agents/` — `revisor-codigo` (diff vs. rules) e
  `auditor-integridade` (os 7 riscos do `docs/06-estrategia-qa.md` §1 contra o diff)
- comandos: `.claude/commands/` — `/planejar-fatia` (quebra em fatias antes de codificar),
  `/validar`, `/reconciliar-migracao`, `/verificar-fechamento`, `/handoff`
- PRD: `docs/02-prd.md` · modelo de domínio: `docs/03-modelo-de-dominio.md` · arquitetura:
  `docs/04-arquitetura.md` · roadmap: `docs/05-roadmap-backlog.md` · QA: `docs/06-estrategia-qa.md`
  · núcleo detalhado: `docs/07-nucleo-v1.md` · diagnóstico da planilha: `docs/01-analise-planilha.md`
- decisões e porquês: `docs/adr/`
- handoff de sessão: `HANDOFF.md`

## Layout do repositório (docs/04-arquitetura.md §5)
```
backend/app/
  api/            # routers finos (APIRouter por módulo, prefixo /api/v1)
  core/           # config.py, security.py, logging.py
  shared/
    domain/       # entidades, value objects, invariantes — não importa FastAPI/SQLAlchemy
    application/  # casos de uso, unit of work, interfaces de repositório
    infrastructure/  # modelos SQLAlchemy, repositórios, storage, Redis, Alembic
  modules/        # identity, clinics, veterinarians, owners, patients, catalog,
                  # pricing, attendances, billing, audit, imports, reports, communications
frontend/src/
  app/            # providers e rotas
  features/       # casos de interação (attendances, billing, ...)
  entities/       # modelos de apresentação
  shared/         # UI e utilidades genéricas
```
Regra de camada: `domain` não importa FastAPI/Pydantic/SQLAlchemy/Redis/SDK externo. Regra de
negócio nunca em router ou componente React.

## Checklist antes de alterar código
Antes de codificar, identifique: problema · ator · permissão · escopo · agregado afetado ·
invariantes envolvidos · estado anterior/posterior · impacto financeiro · impacto no fechamento ·
transação · concorrência · idempotência · migration · contrato de API · auditoria · testes ·
observabilidade · rollback. Se a tarefa mexe em domínio, atualize junto: modelo de domínio,
matriz de permissão, migration, OpenAPI/schema, testes, auditoria, e verifique impacto no
fechamento — mudança parcial que esquece um desses é a forma mais comum de dívida silenciosa
aqui.

## Como trabalho em fatias
Para qualquer tarefa que não seja trivial (mais de ~1 caso de uso/migration/conjunto de testes),
o primeiro passo é propor um plano de fatias verticais pequenas (ver
`.claude/commands/planejar-fatia.md`) e **parar para confirmação antes de codificar**. Não
execute a tarefa inteira em um único bloco silencioso. Depois de cada fatia: rode `/validar` no
escopo tocado, reporte verde/vermelho, e só siga para a próxima fatia com sinal explícito de
continuar. Isso vale mesmo sem o usuário pedir explicitamente — é o modo de trabalho padrão
deste projeto, não uma opção.

## Antes de editar um arquivo existente
- **Quem importa este arquivo?** Pode quebrar quem consome.
- **O que este arquivo importa?** Mudar a interface aqui pode exigir mudar quem chama.
- **Que teste cobre isso?** Rode antes de editar para saber a linha de base.
- **É repositório/caso de uso compartilhado?** (usado por 2+ módulos) → mais lugares afetados.
Edite o arquivo **e** os dependentes na mesma tarefa — nunca deixe import quebrado, schema
desatualizado ou migration pendente para "depois".

## Proibições explícitas (docs/.claude/CLAUDE.md §7 do plano original)
Regra de negócio em router/componente React · modelo SQLAlchemy como response de API · `Session`
de banco global · commit em repository isolado sem unit of work · `float` para dinheiro ·
`MAX + 1` para protocolo · `clinic_id` confiado do body sem autorização · cadastro relacionado
criado silenciosamente · alteração de item fechado · recalcular histórico a partir do catálogo
atual · `except Exception: pass` · `dict[str, Any]` como contrato sem necessidade · migration
destrutiva em uma etapa só · Redis sem TTL · worker persistente dentro de Vercel Function ·
arquivo local como storage durável · teste que mocka toda a persistência crítica e chama isso de
integração · declarar tarefa concluída sem ter executado a validação.

## Saída mínima de uma tarefa
Código · testes · migration quando necessária · schemas de API · autorização · auditoria ·
logs/métricas quando relevante · nota de compatibilidade e rollback.

## Critério de conclusão
Não declare concluído enquanto Ruff, mypy, testes de backend, TypeScript e testes de frontend
relevantes não passarem de verdade. Quando algo não puder ser executado nesta sessão, declare
exatamente o que ficou sem validação — nunca afirme que um comando passou sem tê-lo executado.

## Princípios de código (backend e frontend — nuance de linguagem fica nas rules de estilo)
| Princípio | Regra |
|---|---|
| SRP | Cada função/classe/caso de uso faz **uma** coisa |
| DRY | Duplicou 2x+, extraia |
| KISS | A solução mais simples que resolve, não a mais genérica |
| YAGNI | Não construa para um caso de uso que ninguém pediu (P1/P2 fora de ordem) |

- **Função pequena e de responsabilidade única**; guard clauses em vez de aninhar `if`; poucos
  argumentos (agrupe em objeto/schema quando passar de 3).
- **Composição em vez de herança profunda.**
- Comentário só quando explica o *porquê*; se precisa de comentário para explicar um nome ruim,
  troque o nome.