# ADR-009 — Confirmação de atendimento (protocolo/itens financeiros) e Prévia de Fechamento (Incremento 4.1)

- **Status**: aceita
- **Data**: 2026-07-28
- **Decisores**: Nicolas Nagel (PO/dev), Claude (execução)

## Contexto

O pedido original era "a tela de fechamento financeiro". O roadmap (`docs/05-roadmap-backlog.md`
Fase 4) define o fechamento mensal em três incrementos — Prévia (4.1, read-only), Fechar de fato
(4.2, transacional) e Exceções (4.3, ajuste/reabertura). Esta entrega implementa **só o
Incremento 4.1**, por decisão do usuário.

Investigação prévia (exploração de codebase antes de codar) encontrou um bloqueio real:
`AttendanceRecord` só existia como esqueleto `DRAFT` (`backend/app/modules/attendances/domain/entities.py`)
— sem `AttendanceExam`, sem campos financeiros, sem `billing_competence`, sem protocolo. Sem
isso, a prévia de fechamento não teria dado real para mostrar. A ordem de prioridade do projeto
(`CLAUDE.md`: autenticação → cadastros → **atendimento** → **fechamento**, "é proibido priorizar
módulo... criando atalho que comprometa essa ordem") exige fechar essa lacuna antes, não depois.

Por decisão do usuário, o pré-requisito de attendances entrou **só no backend** (endpoint de
confirmação sem UI) — a tela de confirmação de atendimento fica para uma tarefa futura.

## Decisão

**1. `AttendanceRecord.confirm()` transiciona `DRAFT → CONFIRMED`** com: `AttendanceExam` (itens
com snapshot de `exam_code`/`exam_name`/`price_base` do catálogo, nunca releitura depois),
`subtotal`/`discount_total`/`surcharge_total`/`grand_total` (soma exata dos itens, nunca aceito do
chamador), `billing_competence` (primeiro dia do mês de `service_date`, gravado só na
confirmação), e protocolo completo (`protocol_year`/`protocol_sequence`/`protocol_number`).

**2. Protocolo é transacional de verdade.** Nova tabela `attendance_sequences` (uma linha por
ano) com `SELECT ... FOR UPDATE` dentro da transação de confirmação — nunca `MAX + 1`
(`.claude/rules/database.md`). `UNIQUE(protocol_year, protocol_sequence)` em `attendances`.
Testado sob concorrência real (`asyncio.gather` com múltiplas confirmações simultâneas, unitário
e via QA exploratório contra app real).

**3. Arredondamento de moeda centralizado** em `app/shared/domain/money.py`
(`round_currency`, `ROUND_HALF_UP`, 2 casas) — único ponto do domínio que arredonda, reaproveitado
por `AttendanceExam.__post_init__` e pelo agregado da prévia.

**4. `POST /attendances/{id}/confirm` sem `Idempotency-Key`** — desvio explícito de
`.claude/rules/attendence.md` ("Idempotency-Key obrigatória"), aceito pelo usuário. Ver pendência
1 abaixo.

**5. Prévia de fechamento é inteiramente derivada, nunca persistida.** Novo módulo
`backend/app/modules/billing/` com entidades `ClosurePreview`/`ClosurePreviewItem`/
`ClosurePreviewBlockedItem` — deliberadamente **não** `MonthlyClosure`/`MonthlyClosureItem`, para
não colidir com os nomes que o Incremento 4.2 vai reservar para as entidades persistentes reais.
Nenhuma tabela nova, nenhuma migration para este módulo nesta entrega.

**6. Elegibilidade isolada em `domain/eligibility.py` (`is_eligible`)** como única fonte de
verdade, para o Incremento 4.2 reutilizar sem reimplementar
(`.claude/rules/monthly-closure.md`: "nunca uma versão simplificada que depois diverge").

**7. `GET /closures/preview` é read-only** — sem UoW, sem `AuditEntry`, sem escrita de nenhuma
espécie. Testado explicitamente que a chamada não altera nenhuma tabela.

**8. Dinheiro na API continua `Decimal` serializado como string** (`"300.00"`), nunca número
JSON solto. O usuário pediu inicialmente valores em float; expliquei o conflito com a proibição
explícita do `CLAUDE.md` ("dinheiro nunca é float") e ele optou por manter a API como está,
resolvendo a exibição em R$ só no frontend (`formatCurrencyBRL`, `Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'})`
em `frontend/src/shared/lib/formatters.ts`).

**9. Frontend: `features/billing`** — página de prévia com filtro clínica+mês/ano, cards de
totais e tabela única com badge elegível/bloqueado (motivo visível na linha bloqueada). Rota
`/financeiro/fechamento`; novo grupo "Financeiro" na sidebar, condicionado a `closures.preview`.

## Alternativas consideradas

- **Protocolo simplificado** (ex.: derivado do próprio UUID, sem sequência transacional) —
  oferecida como opção mais barata; **rejeitada pelo usuário**, que escolheu implementar a
  sequência completa já nesta fatia.
- **Idempotência completa na confirmação** — rejeitada nesta rodada por escopo: não existe
  `IdempotencyRecord` genérico no projeto ainda, e o endpoint não tem UI (existe só para dar dado
  real à prévia). Aceito como dívida explícita (pendência 1).
- **API de fechamento devolvendo `float`** — rejeitada por violar `.claude/rules/globals.md`
  ("dinheiro nunca é float"); resolvido mantendo `Decimal`/string na API e formatando só na
  apresentação.
- **Auditar a consulta de prévia** — `docs/03-modelo-de-dominio.md` §8 lista auditoria para a
  *geração do fechamento real*, não para leitura. Decisão: não auditar a prévia nesta entrega
  (é aditivo se precisar mudar depois).
- **Drill-down navegável para tela de atendimento** — rejeitada por escopo: não existe tela de
  atendimento no frontend ainda; o drill-down desta fatia é inline na própria linha da tabela
  (protocolo, paciente, exame).

## Consequências — pendências explícitas

Estas são as lacunas que ficam **abertas de propósito** depois desta entrega, para não virarem
suposição silenciosa depois:

1. **Sem `Idempotency-Key` em `POST /attendances/{id}/confirm`.** Diverge de
   `.claude/rules/attendence.md`. Quando o Registro de Atendimento completo (com UI de
   confirmação) for implementado, isso precisa entrar — inclusive decidir se
   `IdempotencyRecord` é um mecanismo genérico compartilhado (`app/shared`) ou por módulo.
2. **Nenhuma tela de confirmação de atendimento no frontend.** O endpoint existe só para
   popular dado real da prévia. Isso é a próxima peça óbvia do núcleo (Fase 3 do roadmap) a
   priorizar antes do Incremento 4.2.
3. **`surcharge_amount` de item é sempre `0`.** Não há campo em `AttendanceRecord` para marcar um
   atendimento como plantão, então o `Exam.plantao_surcharge` cadastrado nunca é aplicado. Precisa
   de um campo novo (ex.: `is_plantao: bool` ou `collection_method_id`) e de uma decisão de regra
   de negócio (quando algo *é* plantão) antes de fechar essa lacuna.
4. **Prévia não gera `AuditEntry`.** Se o time decidir que consultas de prévia devem ser
   auditadas (ex.: para rastrear quem consultou o quê antes de um fechamento), isso é aditivo,
   não retrabalho — mas hoje não existe.
5. **Permissão de confirmação reaproveita `attendances.update`**, sem `attendances.confirm`
   dedicada. Se algum papel precisar confirmar sem poder editar por outros caminhos (ou
   vice-versa), vai exigir separar a permissão e nova migration de seed.
6. **Drill-down é inline, não navegável.** Fica assim até existir uma tela de detalhe de
   atendimento no frontend.
7. **Sem "diferença em relação a uma prévia anterior"** — citado como opcional em
   `docs/07-nucleo-v1.md` §4.2, sem contrato de API definido. Fica pendente até virar pedido real.
8. **Ano do protocolo é derivado de `service_date.year`, não do momento da confirmação.** Não há
   menção explícita em `docs/03-modelo-de-dominio.md` sobre qual dos dois deveria valer; essa
   convenção foi assumida por consistência com `billing_competence` (também derivado de
   `service_date`). Se o laboratório operar com atendimentos retroativos que atravessam a virada
   do ano, vale confirmar se essa é mesmo a convenção desejada antes de haver volume real.
9. **`MonthlyClosure`/`MonthlyClosureItem` como tabelas persistentes não existem.** O fechamento
   de fato (`POST /closures`, advisory lock, snapshot imutável, `Idempotency-Key`) é inteiramente
   do Incremento 4.2, ainda não iniciado.
10. **Ajuste (`FinancialAdjustment`) e reabertura (`ClosureReopening`) não existem** — Incremento
    4.3, não iniciado.
11. **Achado colateral, não corrigido nesta entrega**: o banco de desenvolvimento local
    (`docker-compose.yml`, volume `vertere_pgdata`) tem dado residual de sessão anterior que
    bloqueia a migration `0017_replace_species_seed` (pacientes referenciando a espécie
    placeholder `"Cão"`, que a migration tenta apagar com `DELETE` — `RESTRICT` na FK impede).
    Isso também derruba `test_import_exams_partial_search_reports_row_errors` em
    `test_catalog_api.py` quando rodado contra esse volume (não em Postgres efêmero limpo, onde a
    suíte passa 100%). Não é regressão desta entrega — é estado pré-existente do volume de dev.
    **Ação pendente**: decidir se o volume de dev local deve ser resetado (é local, não
    produção) ou se a migration precisa de um caminho de backfill para dado pré-existente.

## Verificação

Suíte automatizada verde antes da entrega:

- **Backend**: Ruff (lint + format) e mypy estrito em todo `app/` sem erros; `pytest -m "not
  integration"` — 215 testes; `pytest -m integration` (PostgreSQL real via Testcontainers) — 104
  testes, incluindo concorrência real de protocolo, isolamento multi-clínica, matriz de permissão
  completa (`401`/`403`/`404`/`422`) e teste explícito de que a prévia não persiste nada.
- **Frontend**: `tsc -b` sem erros; `oxlint` sem erros novos; `vitest run` — 91 testes (18
  arquivos), incluindo os 7 novos de `closure-preview-page` (permissão, estados de loading/vazio/
  erro/403, motivo do item bloqueado visível, troca de clínica sem vazar dado da anterior); `vite
  build` de produção ok.
- **QA exploratório real** (`/qa-exploratorio`, não simulado): app rodando contra Postgres
  efêmero, 12 verificações funcionais e de segurança aplicáveis via HTTP real (mass assignment
  bloqueado, SQL injection bloqueado por validação de tipo, XSS não quebra o endpoint, matriz de
  permissão completa, concorrência real de protocolo) — 0 falhas, 2 observações não-bloqueantes
  (headers de segurança ausentes — lacuna pré-existente de todo o projeto, esperada no deploy; e
  isolamento por clínica não se aplica como IDOR nesta fase, já que só existem usuários internos
  `ActorScope.LAB`).
- **Verificação manual em 2026-07-28**, Chrome real: logado como `LAB_ADMIN`, naveguei por todas
  as telas existentes (usuários, perfis, clínicas, veterinários, exames, pacientes) confirmando
  que o dado criado pelo novo fluxo de confirmação não quebra nada a jusante; e testei a tela nova
  ponta a ponta (`/financeiro/fechamento`), selecionando clínica e competência reais e conferindo
  cards e tabela batendo com o `GET /closures/preview` (protocolo `P000001/26`, `R$ 100,00`
  formatado corretamente). Nenhum erro de console em nenhuma das duas sessões.
