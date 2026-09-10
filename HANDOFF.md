# Handoff — 2026-07-30 · fatias 1–7 · worktree não commitado

## Addendum — 2026-09-09 · fatia 08-27 commitada; entrypoint Vercel do backend

`main` está em `959c130`. O worktree que ficou pendente desde o addendum de 2026-08-27 (código
automático/imutável de `Exam`, protocolo `P000001/26`, fix de `row_version`, ajustes de frontend)
foi revalidado do zero (ruff, format-check, mypy, 637 testes backend, oxlint, tsc, 164 testes
frontend — tudo verde) e commitado em `c3a56b7`. CI verde em ambos os pushes.

Em seguida, a pedido do usuário ("continue com o desenvolvimento e os ajustes necessários para
deploy"), foi criado o entrypoint Python do backend para a Vercel (`959c130`):
`backend/app/asgi.py` expõe `app` (instância real, construída do ambiente) referenciado por
`[tool.vercel] entrypoint` em `backend/pyproject.toml`; `backend/vercel.json` exclui
`tests/alembic/scripts` do bundle da função. Dependências continuam só em `pyproject.toml`/
`uv.lock` — Vercel lê isso direto, sem `requirements.txt` duplicado. Teste novo
(`tests/test_asgi.py`) cobre que o módulo expõe a app real via env. Suite completa depois disso:
638 testes backend em 22m38s (mais lento que o normal — sem causa identificada, sem falha).

**Docker Desktop estava totalmente parado** no início desta sessão (por isso os 195 erros de
integração na primeira tentativa) — foi religado manualmente. Containers órfãos de Testcontainers
(`festive_poincare`, `intelligent_northcutt`, `musing_hamilton` — todos "Exited (255)" há 13 dias,
mesma data de uma queda do Docker Desktop) foram removidos; `vertere-qa-pg` (dado real da Fase 4,
porta 55432) e `vertere-postgres` (dev via docker-compose, porta 5432) foram preservados e
religados — `vertere-qa-pg` confirmado com os 2651 atendimentos intactos.

**Pendências reais de deploy — decisão de infra/conta, não de código:**
- criar os dois projetos Vercel (frontend com Root Directory `frontend`, backend com Root
  Directory `backend`) — sem CLI autenticado nesta máquina, não foi possível fazer isso aqui;
- provisionar PostgreSQL gerenciado de produção (com backup/pooler) e apontar `DATABASE_URL`;
- definir o domínio real do frontend em produção e setar `TRUSTED_BROWSER_ORIGINS` no projeto
  backend da Vercel (formato `["https://dominio-real"]`) — sem isso, todo login/mutação autenticada
  falha com `403 CSRF_ORIGIN_FORBIDDEN` (já documentado em `docs/04-arquitetura.md §15`);
- decidir e configurar como as migrations (`alembic upgrade head`) rodam contra o banco de
  produção — como job controlado fora da inicialização da função (nunca dentro do lifespan).

## Addendum — 2026-08-27 · remediações em validação

O `main` está em `a5fbd7a`; o worktree continua não commitado e deve ser preservado. A leva atual
inclui geração automática e imutável de `Exam.code`, apresentação do protocolo como
`P000001/26`, normalização de contratos OpenAPI, uso compartilhado do cliente HTTP no frontend,
correção do cache após login, carregamento inicial/erro do `ExamPicker` e configuração explícita
da origem Vite confiável em desenvolvimento.

Durante QA real foi encontrado e corrigido um bug em `SqlAlchemyExamRepository.save`: o ORM
incrementava `row_version`, mas a entidade usada para montar o DTO permanecia com a versão
anterior. O repositório agora sincroniza a entidade, e um teste de integração executa dois PATCH
consecutivos usando a versão retornada pela primeira resposta.

Validações executadas nesta sessão:

- Ruff check e format-check: verdes, 431 arquivos formatados;
- mypy: verde, 431 arquivos;
- pytest completo antes do ajuste final de `Exam.row_version`: 636 testes passaram em 5m58s;
- após o ajuste: teste de integração novo e testes focados de catálogo verdes;
- frontend: oxlint, TypeScript, 164 testes, build e regeneração OpenAPI/types verdes;
- QA real em PostgreSQL 17 descartável, head Alembic única `0038`: login/CSRF, criação de exame,
  código automático/imutável, 30 criações concorrentes com 31/31 códigos distintos no banco,
  dois PATCH consecutivos retornando versões 3 e 4, protocolo em confirmação/leitura/listagem e
  preview de fechamento, formulário desktop/mobile, auditoria, headers de segurança e PII grep
  verdes;
- backend, Vite, container e logs temporários do QA foram encerrados/removidos.

Limites declarados do QA: não foi executada a matriz integral dos 13 itens de segurança, o retry
do `ExamPicker` após remover a interceptação não terminou, o clique final de criação do exame no
navegador excedeu o tempo (API real e formulário foram validados separadamente), e o protocolo no
financeiro foi verificado no preview, não em um fechamento definitivo.

Próxima fatia recomendada — `row_version` transversal: a auditoria read-only confirmou o mesmo
DTO desatualizado em clínicas, pacientes, veterinários e categorias de exame. Em identidade,
ativação/desativação devolvem a versão default `1`, enquanto `AssignRole` compensa manualmente o
repositório. Corrigir as cinco implementações de `save`, remover a compensação e adicionar testes
API encadeados. Não iniciar sem o checkpoint explícito exigido pelo `AGENTS.md`.

## Estado consolidado

O `main` permanece em `eb97cda`. Todo o trabalho descrito abaixo está no worktree e ainda não foi
commitado. Alterações preexistentes foram preservadas; não usar reset/checkout sobre este estado.

- **Fatia 1 — identidade e autorização:** sessão opaca, usuários, papéis, permissões e auditoria.
- **Fatia 2 — clínicas:** cadastro, ativação/inativação e endereços.
- **Fatia 3 — veterinários:** cadastro, autonomia e vínculo N:N com clínicas.
- **Fatia 4 — pacientes:** espécies, paciente e tutor embutido.
- **Fatia 5 — catálogo:** categorias, exames, preço embutido e importação CSV.
- **Fatia 6 — núcleo de atendimento:** rascunho/listagem/detalhe, confirmação, itens, protocolo,
  idempotência, cancelamento/edição/timeline e prévia de fechamento.
- **Fatia 7 — abertura operacional:** `/operacao/novo` com permissão `attendances.create`, clínica
  ativa, veterinário ativo autônomo ou vinculado à clínica, busca paginada de pacientes ativos,
  aviso de possível duplicidade, criação rápida condicionada a `patients.manage` preservando o
  formulário, data, observações, envio a `POST /api/v1/attendances/drafts` e retorno a `/operacao`.
  Exames, preços, plantão e método de coleta não fazem parte desta fatia.

O worktree também contém o pipeline de importação da planilha, migrations 0016–0021 e mudanças de
domínio/backend iniciadas antes desta revisão. Esses arquivos não foram refeitos nem descartados.

## Harness compartilhado

- `AGENTS.md` é a fonte canônica. `CLAUDE.md` é um adaptador mínimo com `@AGENTS.md`.
- Rules padronizadas como `00-global.md` a `13-monthly-closure.md`; `/testar-app` foi movido para
  `.claude/commands/testar-app.md`; `system-design/SKILL.md` teve o casing corrigido.
- `.agents/skills/` contém wrappers mínimos para descoberta nativa pelo Codex; a fonte continua em
  `.claude/skills/`.
- Hooks não dependem mais de `jq`: `.claude/hooks/read-hook-json.py` lê payloads Edit/Stop. O Stop
  executa Ruff, Ruff format-check e mypy.
- `/validar`, hooks e CI usam os mesmos gates; o cache do CI aponta para `uv.lock` na raiz.
- Busca em referências ativas não encontrou nomes antigos; ADRs e o plano histórico foram mantidos.

## Validações executadas nesta sessão

- `uv run ruff check backend`: **verde**.
- `uv run ruff format --check backend`: **verde**, 340 arquivos. Quatro testes de identidade que
  já estavam fora do formato foram corrigidos.
- `uv run mypy backend`: **verde**, 340 arquivos.
- Alembic em PostgreSQL descartável limpo, via `backend/tests/integration/test_database.py`:
  **3 passed**.
- Pytest completo: **423 passed** e **1 erro exclusivamente no teardown do Testcontainers** após
  11m24s; o Docker Desktop excedeu 60s ao remover um container. Reexecução isolada de
  `test_billing_api.py`: **9 passed**. Não houve falha funcional/de asserção.
- Frontend: oxlint **sem erros** (2 warnings preexistentes de fast refresh), TypeScript **verde**,
  Vitest **21 arquivos / 107 testes passed**, build Vite **verde**.
- Build: chunk principal **543,87 KB** (gzip 155,41 KB), mantendo o alerta >500 KB.
- Hooks: payloads Edit/Stop funcionaram com `jq` ausente; o hook Python formatou o arquivo temporário
  correto (`x=  1` → `x = 1`), removido após o teste.

## QA real e arquivos temporários

Outra sessão Claude retomou QA durante esta revisão e iniciou backend em `127.0.0.1:8123` e Vite em
`localhost:5183`, criando `backend/alembic.ini.qa` e `frontend/vite.qa.config.ts`. Esses processos e
arquivos foram preservados. Esta sessão não recebeu o relatório final do navegador; portanto não
afirma como verificados os itens visuais/responsivos ou a inspeção direta do banco. Capturar o
resultado da sessão Claude antes de remover qualquer auxiliar de QA.

## Bloqueadores e backlog priorizado

1. **Bloqueador de produção — segurança/tenant:** isolamento por clínica/membership ainda não está
   implementado; consultas de atendimento não restringem tenant. Abrir uma fatia própria e não
   corrigir silenciosamente dentro da Fatia 7.
2. **Performance backend/frontend:** listagem monta nomes com múltiplos joins client-side e limita
   cadastros auxiliares aos primeiros 100 registros.
3. **Performance frontend:** aplicar lazy loading/code splitting e revisar imports/assets de fontes;
   o bundle principal medido está em 543,87 KB.
4. **Infra de testes:** o conjunto completo leva ~11 minutos por criar containers por módulo e pode
   falhar no teardown do Docker Desktop. Consolidar fixtures/containers sem reduzir cobertura.
5. **Verificação de interoperabilidade:** abrir uma sessão nova de Codex e conferir a descoberta de
   `AGENTS.md`/wrappers; no Claude, confirmar `/memory` apontando `AGENTS.md`. Não foi possível
   provar isso de dentro desta mesma sessão.

## Próximo passo

Capturar/concluir o QA real já iniciado, resolver qualquer achado sem ampliar o contrato do backend,
reexecutar os gates afetados e então seguir para a **Fatia 8** (itens/exames da abertura de

---

## Addendum — 2026-07-31 · tela de confirmação/detalhe de atendimento (fatias separadas)

> Sessão distinta da acima (numeração de fatia própria: 1–7 já cobriam identidade/cadastros/
> atendimento-núcleo; esta trilha tratou especificamente da tela `/operacao/:attendanceId`).
> Não reconcilia com a numeração da seção anterior deste arquivo — mantido como registro aditivo,
> sem reescrever o que já estava documentado acima.

**Feito nesta trilha, em ordem:**
1. Tela de confirmação de atendimento (`AttendanceConfirmationForm`) — seleção de exame, total
   calculado no backend via `/preview`, confirmação com `Idempotency-Key`.
2. Ações de cancelar/editar observações/timeline na tela de detalhe
   (`AttendanceDetailPage`/`AttendanceReadonlyDetail`) — `POST /cancel`, `PATCH` (notas em
   `CONFIRMED`), `GET /timeline` paginado.
3. **Gap fechado**: edição completa do cabeçalho (clínica/veterinário/paciente/data) enquanto o
   atendimento está `DRAFT` — endpoint `PATCH` já suportava desde a fatia de backend; só não havia
   UI. Componente novo: `attendance-header-details.tsx` — some/leitura sempre (clínica, veterinário,
   paciente, data), edição completa só quando `status === 'DRAFT'` **e** `attendances.update`;
   read-only sempre em `CONFIRMED`/demais estados, reforçado pelo próprio backend
   (`AttendanceRecord.update_fields`: fora de `DRAFT`, só `notes` é aceito — testado em QA real via
   `curl`, retorna `422 VALIDATION_ERROR`).
   - `attendances-api.ts`: função `updateAttendanceNotes` generalizada para `updateAttendance(id,
     rowVersion, input)`, aceitando qualquer subconjunto de campos — usada tanto pelo editor de
     observações (`CONFIRMED`) quanto pelo editor completo (`DRAFT`).
   - Hook único `use-update-attendance-mutation.ts` substituiu o hook específico de notas.
   - Reutiliza `PatientPicker`, `SelectField` e os hooks de clínica/veterinário já existentes do
     formulário de rascunho — sem endpoint novo no backend.
   - **Pendência sinalizada, não corrigida nesta fatia**: `PatientPicker` dentro do editor de
     cabeçalho não oferece criação rápida de paciente (`canCreate={false}`) — só troca entre
     pacientes já cadastrados. Criar paciente novo durante a edição do cabeçalho de um atendimento
     já existente fica para uma fatia futura, se necessário.

**Bug encontrado e corrigido durante QA real (não relacionado ao gap acima):**
`formatDate()` em `shared/lib/formatters.ts` interpretava string de data pura (`"2026-07-01"`,
sem componente de hora) como meia-noite UTC — em fuso atrás de UTC (America/Sao_Paulo), exibia o
dia anterior (`billing_competence: "2026-07-01"` aparecia como "30 de jun."). Corrigido: string
`YYYY-MM-DD` sem hora é lida como data de calendário local, não como instante UTC. Teste de
regressão em `formatters.test.ts`.

**Gate final desta trilha:** tsc limpo, oxlint sem erros novos (2 warnings pré-existentes de fast
refresh, não tocados), Vitest **124 testes / 21 arquivos passed**, `vite build` verde. QA real
executada contra Postgres descartável + backend real (algumas etapas via `curl` direto quando o
Chrome/Docker Desktop caíram no meio da sessão) — cobertura confirmada: fluxo de confirmação,
cancelamento (incluindo bloqueio de recancelar/editar após `CANCELLED`), edição de observações
com conflito de `row_version` (`409`), timeline com diff de auditoria, edição completa do
cabeçalho em `DRAFT` (clínica → filtra veterinário vinculado, troca de paciente, data), bloqueio
de edição de cabeçalho pós-confirmação reforçado no backend, negação de permissão (`403`) para
usuário sem `attendances.cancel`/`attendances.update`.

**Pendências não-bloqueantes acumuladas (todas as fatias desta trilha):**
- Viewport mobile/responsivo nunca testado nas telas de atendimento.
- Criação rápida de paciente indisponível no editor de cabeçalho de atendimento já existente
  (só no formulário de rascunho novo).
- Preço nulo para usuário sem `pricing.read` não foi reverificado nesta trilha (padrão herdado,
  não uma regressão encontrada).
- Isolamento de tenant por clínica/membership (já registrado como bloqueador de produção na seção
  anterior deste arquivo) segue em aberto — não tocado por esta trilha.

**Próximo passo desta trilha:** planejar o Incremento 4.2 do fechamento mensal (`POST
/closures`, lock, snapshot, imutabilidade, auditoria, exportação simples) — ainda não iniciado.
atendimento). Antes de declarar o núcleo pronto para produção, executar a fatia separada de
isolamento por tenant.
