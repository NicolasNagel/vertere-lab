# ADR-005 — Preço embutido em `Exam`, sem `PriceTable`/vigência nem `ExamPanel`

- **Status**: aceita
- **Data**: 2026-07-25
- **Decisores**: Nicolas Nagel (PO/dev), Claude (execução)

## Contexto

Fase 2 do roadmap (`docs/05-roadmap-backlog.md` §4), itens 7 (catálogo de exames e painéis) e 8
(tabelas de preço e vigência) — próximo depois de clínicas, veterinários, vínculo
veterinário-clínica, espécies e pacientes (ADR-004). Ao contrário dos itens anteriores, este tem
mockup e spec completos: `assets/features/screens/6-cadastro-de-exames.html` +
`assets/features/screens/spec-pages.md:376-451` ("Tela de Cadastro de Exames & Preços").

O modelo de domínio (`docs/03-modelo-de-dominio.md` §1, contexto Master Data) lista `Exam`,
`ExamPanel`, `ExamPanelItem`, `PriceTable` e `PriceTableItem` como entidades separadas — sugerindo
preço com tabela própria e vigência por período, e exames agrupáveis em painéis/combos. A spec da
tela, porém, descreve preço como **campos diretos do cadastro de exame** (`price_base_cents`,
`plantao_surcharge_cents`/`plantao_surcharge_percent` no payload de `POST /exams`), sem qualquer
menção a vigência, histórico de tabela de preço ou painéis de exames. Se nada fosse decidido, a
implementação ficaria ambígua entre seguir `docs/03` à risca (criar `PriceTable`/`PriceTableItem`
e `ExamPanel`/`ExamPanelItem` sem UI nem caso de uso que os use) ou seguir o mockup silenciosamente
— desviando de dois documentos de referência sem registro, o que a prática deste projeto proíbe
(ver ADR-002, ADR-004 para o mesmo tipo de decisão já tomada para `ClinicContact` e `Owner`).

Três decisões adicionais surgiram durante a execução, sem resposta pronta em `docs/`.

## Decisão

**1. Preço embutido em `Exam`, sem `PriceTable`/`PriceTableItem`.** `price_base`,
`plantao_surcharge_fixed` e `plantao_surcharge_percent` são colunas diretas de
`exams` (`backend/app/modules/catalog/infrastructure/models.py`). Não existe conceito de vigência
por período — mudar o preço de um exame altera o valor vigente imediatamente para novos pedidos,
sem afetar atendimentos já confirmados (que preservam snapshot próprio quando o Registro de
Atendimento existir, Fase 3 — `docs/03-modelo-de-dominio.md` §3, já contempla isso independente
de como o catálogo guarda o preço atual).

**2. Tipo `Decimal`/`NUMERIC(14,2)`, não inteiro em centavos.** A spec usa nomes de payload em
centavos (`price_cents`, `plantao_surcharge_cents`) mas o projeto tem uma regra global não
negociável (`.claude/rules/globals.md`, "Dinheiro": *"Python `Decimal`; PostgreSQL
`NUMERIC(14,2)`. Nunca `float`."*). Os campos reais são `price_base`/`plantao_surcharge_fixed`
(`NUMERIC(14,2)`) e `plantao_surcharge_percent` (`NUMERIC(5,2)`), valores em reais/percentual
direto, não centavos. Divergência deliberada da nomenclatura do mockup, não um desvio da regra do
projeto.

**3. `ExamPanel`/`ExamPanelItem` fora de escopo.** Nenhuma tela ou spec descreve painéis/combos de
exames — não existem tabelas, casos de uso nem endpoints para isso nesta fatia.

**4. Importação de catálogo via CSV (`POST /exams/import`) adiada.** Decisão explícita do usuário:
funcionalidade suficientemente separada (parse de arquivo, relatório de erro por linha) para
justificar sua própria fatia futura, depois do CRUD básico estar estável em produção.

**5. `ExamCategory` como módulo próprio com CRUD completo, sem tela dedicada.** Decisão explícita
do usuário — diferente do padrão "seed fixo sem endpoint" adotado para `Species` (Fatia 1 de
Pacientes): categoria tem endpoints de gestão reais (`POST/GET/PATCH /exam-categories`,
`POST .../deactivate`), mas nenhuma tela própria de listagem — é exposta só como select + criação
rápida inline no formulário de Exame (`frontend/src/features/catalog/components/exam-form.tsx`).

**6. Mapeamento `VIEW_EXAM_PRICES` (spec) → `pricing.read` (catálogo real).** A spec exige "preço
só é exibido para quem tem `VIEW_EXAM_PRICES`, mesmo com `EXAM_VIEW`" — esse nome de permissão não
existe no catálogo real (`docs/07-nucleo-v1.md` §2.2). Mapeado para `pricing.read` como gate
adicional sobre `catalog.read`: o backend **omite completamente** os campos de preço do DTO/
response quando o ator não tem `pricing.read` (`exam_to_dto(..., include_price=...)`,
`backend/app/modules/catalog/application/mappers.py`) — nunca os retorna mascarados nem depende
do frontend para escondê-los. Mesmo padrão de divergência de nome de permissão já documentado no
ADR-003 (`VET_VIEW`/`VET_EDIT` → `veterinarians.read`/`manage`).

**7. `GET /species` deixou de exigir `patients.read`.** Efeito colateral necessário: o formulário
de Exame também precisa listar espécies (para o campo "espécies atendidas"), e um perfil como
`FINANCE` puro tem `catalog.manage`/`pricing.read` mas não necessariamente `patients.read`. Como
`Species` é dado de referência estático e não sensível, sem tela ou ação própria (ADR-004 já
estabeleceu isso), a exigência de permissão foi removida — `GET /species`
(`backend/app/modules/patients/api/routers.py`) agora só exige autenticação (`get_current_user`),
não uma permissão de recurso específica.

## Alternativas consideradas

- **`PriceTable`/`PriceTableItem` com vigência desde já** — rejeitada por YAGNI: nenhuma tela ou
  caso de uso usa histórico de tabela de preço nesta fase; construiria uma camada extra de
  mapeamento e casos de uso para uma cardinalidade (preço por período) que ninguém pediu ainda.
- **Preço em centavos (inteiro)**, seguindo a nomenclatura literal da spec — rejeitada: contraria
  a regra não negociável de `.claude/rules/globals.md` sobre `Decimal`/`NUMERIC`; centavos como
  inteiro evitaria erro de ponto flutuante mas o projeto já decidiu a forma (Decimal explícito) em
  vez dessa alternativa comum.
- **Nova permissão dedicada `species.read`** — rejeitada em favor de abrir `GET /species` para
  qualquer autenticado: criar uma permissão só para um endpoint de leitura de dado estático e não
  sensível adicionaria entrada ao catálogo (`docs/07-nucleo-v1.md` §2.2) sem proteger nada real.

## Consequências

- `docs/03-modelo-de-dominio.md` fica **desatualizado nesta fatia especificamente** —
  `PriceTable`, `PriceTableItem`, `ExamPanel` e `ExamPanelItem` seguem listados mas não
  implementados. Mesma situação já registrada em ADR-002 e ADR-004: aceitável enquanto
  documentado.
- Se um requisito real de vigência de preço surgir (ex.: reajuste anual programado, preço
  diferente por competência), a migração é aditiva: criar `price_tables`/`price_table_items`,
  popular com o preço atual de cada `Exam` como "tabela vigente inicial", manter
  `exams.price_base` como cache/fallback até o novo fluxo estar validado — sem quebrar exames já
  cadastrados.
- Se um requisito real de painéis de exames surgir, `ExamPanel`/`ExamPanelItem` entra como módulo
  novo referenciando `Exam` por ID — não precisa alterar nada do que existe hoje.
- `GET /species` aberto a qualquer autenticado é uma superfície um pouco mais ampla do que
  "permissão explícita por padrão" — aceitável porque o dado é público dentro do sistema (nenhuma
  informação sensível, sem PII, sem valor financeiro) e não tem ação de escrita associada.
- Qualquer papel com `catalog.manage` mas sem `pricing.read` (hoje: `TECHNICAL_MANAGER`) pode criar/
  editar um exame definindo preço, mas a resposta da API não devolve esse preço de volta — ao
  editar depois, o campo de preço no formulário aparece vazio (não pré-preenchido), exigindo
  redigitação. É uma tensão inerente ao modelo de permissão (escrever um valor que não se pode
  ler de volta), não um bug — registrado aqui como comportamento esperado, não como pendência.

## Verificação

Suíte automatizada verde antes da entrega: backend (`ruff check` + `ruff format --check` + mypy
estrito em `domain`/`application` + pytest — 152 testes, incluindo integração com Postgres real
via Testcontainers cobrindo criação/edição/inativação de categoria e exame, código duplicado,
adicional de plantão mutuamente exclusivo — `422` quando os dois tipos são enviados —, e
visibilidade de preço condicionada a `pricing.read`); frontend (`tsc -b` + oxlint + vitest — 58
testes, incluindo criação de exame com categoria e espécie, bloqueio de submissão sem espécie
selecionada, e exibição/ocultação do preço conforme a permissão do usuário logado — `vite build`
de produção ok).

Verificação manual **não realizada nesta sessão** (sem ambiente de navegador disponível) —
pendente antes de considerar esta fatia definitivamente encerrada, conforme a Definição de Pronto
(`.claude/rules/definicao-de-pronto.md`, item 13).
