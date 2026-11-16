# Plano — Exames & Preços (redesign) e regras de cobrança por clínica

Status: **proposta, aguardando confirmação** (AGENTS.md: parar antes de codificar). Nada deste
plano foi implementado. Origem: `docs/pendencias-redesign-operacao.md` ("Telas de Exames & Preços
ainda no visual antigo", "Futuro: regras de cobrança por clínica"), ADR-005 e ADR-006.

## 0. Estado atual (verificado no código)
- Preço mora em `Exam` (ADR-005): `price_base`, `price_valid_from/to` (migration 0027), uma única
  janela, **sem histórico**. `has_price_on(service_date)` decide se o exame pode entrar no atendimento.
- Taxa de plantão: `OnCallFeeSetting` (editada com `pricing.manage`), valor fixo por atendimento.
- Pacote = `Exam` com `component_ids`, preço próprio (migration 0039).
- Backend omite preço sem `pricing.read` (`exam_to_dto(include_price=...)`).
- **Lacuna de permissão:** `UpdateExamUseCase` exige só `catalog.manage` para mudar `price_base` e
  vigência; `pricing.manage` só protege a taxa de plantão. Hoje quem edita cadastro edita preço.
- Atendimento guarda snapshot por item (`AttendanceExam`); fechamento lê `grand_total` vivo do
  atendimento e ajustes cobrem correções (invariante: contribuição do fechamento = `grand_total`).
- Tela: `exams-page.tsx` + sidebar de categorias/espécies + cartões de resumo + painel de plantão +
  tabela; formulários separados (`exam-form-page`, pacote). Visual antigo, filtro de categoria/espécie
  feito no cliente sobre página carregada.

## A. Redesign da tela Exames & Preços
Princípios (memória do projeto): render primeiro, sem enfeite, 1 tela por vez com captura, contrato
visual antes de codar, tabela ≤ 460 px de largura útil por coluna crítica, botões `Button` padrão.

1. **Estrutura:** cabeçalho (título + ações: Importar, Novo pacote, Novo exame) → barra de filtros
   (busca, categoria, espécie, status, "sem preço vigente") → tabela única. Sem cartões de resumo
   decorativos; manter só contagem no rodapé da tabela. Sidebar de categorias vira filtro (Select).
2. **Tabela:** Código · Nome (+ badge Pacote) · Categoria · Espécies · Preço vigente · Vigência ·
   Status · Ações. Coluna de preço só com `pricing.read`; sem ela a coluna some (como na lista de
   atendimentos). Filtros e contagens **no servidor** (hoje são do cliente; resolve a pendência da
   "página de 100").
3. **Editar tudo:** linha clicável abre o detalhe do exame com blocos "Editar" por seção (padrão do
   detalhe de atendimento): Identificação, Categoria/Espécies, Composição (pacote), **Preço e
   vigência**, Status. Cada salvamento: `row_version`, motivo obrigatório para preço/vigência/status,
   diff no `audit_log`. Mudar preço **não** altera atendimento já confirmado (snapshot).
4. **Preço e histórico (bloco):** mostra preço vigente hoje e a lista de períodos (ver B). Sem
   `pricing.manage` o bloco é leitura.
5. **Taxa de plantão:** sai de cima da tabela e vira aba/seção "Taxas" da mesma tela, mesmo padrão
   de bloco com Editar + motivo.
6. **Regras por clínica:** aba "Regras de cobrança" (ver B), lista e edição no mesmo padrão.
7. **Estados:** loading, vazio, erro, 403, conflito de versão (recarregar). Axe + overflow em
   desktop/tablet/mobile (`e2e/exams-prices.spec.ts`), como feito em `attendance-correction`.
8. **Correção de permissão (parte da fatia 1):** alterar preço/vigência passa a exigir
   `pricing.manage` (hoje `catalog.manage`). Sem permissão nova. Quem tem só `catalog.manage` edita
   nome/categoria/espécies, não valor — mesma lógica de "sem ver/gerir valor, não altera valor".

## B. Regras de cobrança por clínica
### B.1 Dois conceitos distintos (decidir antes de modelar)
- **Histórico de preço do exame** (preço mudou em 01/03; atendimento de fevereiro lançado depois
  deve usar o preço de fevereiro): hoje impossível, só há uma janela.
- **Regra por clínica** (Bicho Urbano +R$ 5 em Check-up 1/2/3 para cães): já decidida em 14/11
  (cobra UMA vez por atendimento, soma com plantão, acumula entre regras, desconto manual não afeta,
  vale a partir da vigência).
Os dois são independentes e entram em fatias separadas.

### B.2 Modelo proposto (ADR-013, a escrever na fatia 2; substitui o ponto 1 do ADR-005)
- `ExamPrice` (tabela filha de `exams`): `exam_id`, `price`, `valid_from`, `valid_to|null`,
  `created_by`, `reason`. Períodos do mesmo exame **não se sobrepõem** (constraint `EXCLUDE USING
  gist` com `daterange`, ou validação no caso de uso + índice). `exams.price_base`/`price_valid_*`
  viram a projeção do período vigente (ou são removidos após backfill, ver B.4).
- Resolução de preço no atendimento: `price_on(service_date)` busca o período que cobre a data;
  sem período = "sem preço vigente" (comportamento atual). Fecha a limitação conhecida de inclusão
  retroativa de exame.
- `ClinicBillingRule`: `clinic_id`, `name`, `target_type` (EXAM | PANEL | CATEGORY | ALL),
  `target_id|null`, `species_id|null`, `effect` (FIXED_SURCHARGE | PERCENT_SURCHARGE | DISCOUNT |
  FIXED_PRICE), `amount`, `valid_from`, `valid_to|null`, `is_active`, `row_version`.
  Escopo inicial mínimo proposto: **só acréscimo fixo por atendimento** (FIXED_SURCHARGE) — o que o
  financeiro pediu. Demais efeitos ficam previstos no enum mas fora da primeira entrega (YAGNI).
- Snapshot no atendimento: tabela `attendance_billing_rule_applications` (`attendance_id`,
  `rule_id`, `rule_name`, `amount`, `applied_at`) gravada na confirmação; `grand_total` passa a
  `itens − descontos + plantão + Σ regras`. Fechamento continua lendo `grand_total` (nada muda no
  contrato do fechamento); o rótulo da regra aparece no detalhe/exportação.
- Recalcular regra em **correção** de atendimento (data, clínica, exames mudam): reavaliar com a
  regra **vigente na data do serviço** e gravar nova aplicação; a diferença de `grand_total` já vira
  `FinancialAdjustment` pelo caminho existente (`closure_settlement`). Regra reajustada depois não
  retroage a atendimento já confirmado, exceto se o usuário corrigir esse atendimento (aí vale a
  regra vigente na data do serviço — a confirmar, pergunta 3).

### B.3 Permissões, auditoria
- `pricing.read` ver preços e regras; `pricing.manage` criar/editar/inativar período de preço e
  regra (já existe no seed para FINANCE e LAB_ADMIN; nenhuma permissão nova).
- `audit_log`: `pricing.exam_price_set`, `pricing.rule_created/updated/deactivated` com antes/depois
  e motivo. Regra e período nunca são apagados (inativar/encerrar vigência).
- Clínica nunca vê regra de outra clínica; usuário de clínica não lê regras nem preços de catálogo
  (mesma política atual de `pricing.read`). Valores seguem ocultos sem `pricing.read`.

### B.4 Migration e backfill (reversíveis, sem passo destrutivo único)
1. Migration A (expand): cria `exam_prices`; backfill 1 período por exame existente a partir de
   `price_base`, `price_valid_from`, `price_valid_to`, `reason = 'backfill ADR-013'`.
   Mantém as colunas antigas lidas por compatibilidade.
2. Código passa a resolver preço por `exam_prices`; colunas antigas ficam como espelho do vigente.
3. Migration B (contract), em release posterior: remove as colunas antigas. `downgrade` recria e
   preenche a partir do período vigente. Teste de rollback com dados, igual ao da 0039.
4. Migration C: `clinic_billing_rules` + `attendance_billing_rule_applications` (tabelas novas, sem
   backfill; atendimentos antigos ficam sem aplicação = total inalterado).

### B.5 Teste de reconciliação (obrigatório, regra "novo valor financeiro")
- Propriedade (Hypothesis): `grand_total = Σ itens − Σ descontos + plantão + Σ regras aplicadas`
  para combinações válidas; regra cobra no máximo 1× por atendimento mesmo com vários exames-alvo
  e quantidade > 1; pacote conta como um exame e componente não dispara a regra.
- Integração (Postgres real): confirmar com regra → snapshot gravado e `grand_total` correto;
  reajustar regra depois → atendimento confirmado não muda; fechar período → soma do fechamento ==
  Σ `grand_total`; corrigir atendimento fechado (trocar exame-alvo) → ajuste = diferença exata;
  mover para fora do período reverte regra no fechamento antigo; escopo de clínica (IDOR) nas
  telas/endpoints de regra; mass assignment (`amount`, `clinic_id`) rejeitado; sem `pricing.read`
  a API não devolve valor de regra aplicada (reuso da redação de dinheiro feita em `f9af2d6`).
- Migração: reconcilia que `Σ preço vigente por exame` pós-backfill == antes.

## C. Fatias verticais (cada uma: plano curto → código → /validar → QA real → parar)
1. **Tela Exames & Preços no padrão atual + gate `pricing.manage` no preço.** Tabela única com
   filtros no servidor, detalhe com blocos Editar + motivo, plantão em aba. Sem mudar modelo.
   Teste: permissão (catalog.manage sem pricing.manage não muda preço), auditoria com diff,
   conflito de versão, axe/overflow, vitest dos 5 estados.
2. **ADR-013 + histórico de preço (`exam_prices`).** Migration A + backfill, resolução por data de
   serviço, bloco "Preço e vigência" com lista de períodos, atendimento retroativo usa o preço da
   época. Teste de rollback com dados e de não sobreposição de períodos.
3. **Regras por clínica — backend.** `clinic_billing_rules`, caso de uso de aplicação na confirmação
   e na correção, snapshot, `grand_total` com regras, reconciliação com fechamento.
4. **Regras por clínica — tela.** Aba "Regras de cobrança" (lista, criar, editar, inativar com
   motivo), visão da regra aplicada no detalhe do atendimento (linha "Regra: Bicho Urbano +R$ 5,00").
5. **Contract da migration (remover colunas antigas) + docs** (matriz de permissão, modelo de
   domínio, ADR-005 marcado como substituído parcialmente).

Ordem sugerida: 1 → 2 → 3 → 4 → 5. A 1 é independente e entrega valor sozinha; 3 depende da 2 só
se a regra precisar de preço histórico (não precisa; pode inverter 2 e 3 se o financeiro priorizar
a regra do Bicho Urbano).

## D. Riscos
- **Total muda de fórmula:** qualquer erro em `grand_total` vaza para fechamento e ajustes.
  Mitigação: reconciliação por propriedade antes de ligar a regra; feature controlada por existência
  de regra ativa (sem regra, caminho idêntico ao atual).
- **Backfill de preço:** exame com `price_valid_to` no passado ou janela invertida. Mitigação:
  relatório de anomalias na migration (dry run) antes de aplicar.
- **Sobreposição de períodos sob concorrência:** dois usuários cadastrando período. Mitigação:
  constraint de exclusão no Postgres + teste concorrente real.
- **Reavaliar regra ao corrigir atendimento fechado** gera ajustes que o financeiro não espera.
  Mitigação: aviso explícito na tela de correção ("esta correção muda a regra X: +R$ 5,00").
- **Pacote e regra no nível do atendimento:** interpretação "pacote conta como um exame" ainda
  marcada "confirmar ao desenhar" no doc de pendências.
- Intermitência conhecida de um teste vitest do painel de plantão pode reaparecer ao mover o painel.

## E. Perguntas que mudam a decisão
1. **Histórico de preço agora ou depois?** Se retroagir atendimento (lançar/editar fevereiro com
   preço de fevereiro) é frequente, a fatia 2 sobe de prioridade; se o preço quase não muda, dá para
   adiar e só trocar a janela única por "preço novo a partir de DD/MM" sem tabela.
2. **Regras por clínica vêm antes do histórico de preço?** (Bicho Urbano está pagando a diferença
   hoje.) Se sim: ordem 1 → 3 → 4 → 2.
3. **Ao corrigir atendimento antigo, qual regra vale: a vigente na data do serviço ou a gravada na
   confirmação?** Recomendação: vigente na data do serviço, com aviso. Muda o comportamento do ajuste.
4. **Efeitos além de acréscimo fixo** (percentual, desconto, preço fixo por clínica) são necessários
   já? Recomendação: não; só acréscimo fixo na primeira entrega.
5. **Preço diferente por clínica** (tabela por clínica, não só acréscimo) existe de fato? Se sim, o
   modelo muda (`ExamPrice` ganha `clinic_id` ou entra `PriceTable`) e vira ADR maior; se o caso é
   sempre "preço padrão + ajuste", `ClinicBillingRule` basta.
6. **Quem edita preço:** só `pricing.manage` (recomendado, hoje `catalog.manage` também edita). Há
   perfil que depende do comportamento atual?
7. **Usuário de clínica deve ver, no próprio atendimento, o rótulo da regra aplicada?** Hoje clínica
   não vê valores de catálogo; define a redação da regra no detalhe.

## F. Decisões do usuário (2026-11-15)
- Pergunta 1 (retroagir preço é frequente?): **não**. O histórico de preço (fatia 2, ADR-013) deixa de ser prioridade e fica para depois.
- Pergunta 2 (tabela de preço própria por clínica?): **não**. O modelo é "preço padrão + regra/ajuste por clínica"; não há tabela própria.
- Ordem resultante: fatia 1 (tela + `pricing.manage`) → 3 (regras por clínica, backend) → 4 (regras por clínica, tela) → 2 (histórico) → 5 (limpeza).
- Perguntas 3, 4, 5 (parte respondida), 6 e 7 seguem abertas; as recomendações do plano valem até decisão contrária.

## G. Módulo de Taxas — decisões e implementação (fatias 3+4, 2026-11-15)
Decisões do usuário: taxa de urgência é **valor fixo**; taxa da clínica é **valor fixo que soma ao total do atendimento**, com datas de vigência; plantão + urgência + taxa da clínica **somam entre si**.

- **Modelo:** `urgency_fee_settings` (linha única), `clinic_fee_rules` (clínica, nome, valor, `valid_from`/`valid_to`, ativa) e, em `attendances`, `is_urgent`, `urgency_fee`, `clinic_fee`, `fee_lines` (JSONB, snapshot por linha: tipo, rótulo, valor, regra). Migration `0041`, reversível.
- **Total:** calculado no backend = subtotal dos exames + plantão + urgência + taxas da clínica vigentes em `service_date`. Linhas com valor zero não aparecem.
- **Snapshot / sem retroação:** atendimento confirmado mantém as taxas de quando foi confirmado; mudar o cadastro não o altera. Só uma correção que mude tipo de serviço, urgência, clínica ou data de atendimento reprecifica as taxas (auditado, com o motivo).
- **Permissões e auditoria:** `pricing.read` para ver valores (sem ela a API devolve `null` nos valores de taxa); `pricing.manage` para alterar. Toda alteração (plantão, urgência, regra da clínica) exige **motivo** e grava `audit_log` com antes/depois; `row_version` → 409 em edição concorrente. Regras por clínica só no escopo laboratório.
- **Fechamento:** o fechamento continua somando `grand_total`; o campo `on_call_fee_total` agora carrega plantão + urgência + taxa da clínica. **Pendência:** o rótulo "plantão" no CSV/prévia do fechamento está impreciso e deve virar "taxas".
- **Tela:** aba "Taxas" em Exames & Preços com subcadastros Plantão, Urgência e Por clínica (tabela, modal de edição com motivo, botão "Nova taxa"). Registro de atendimento ganha o marcador "Atendimento urgente" e o resumo de valor lista cada taxa.
- **Fora desta entrega:** regra da clínica direcionada a exame/categoria; `Idempotency-Key` no `POST /clinic-fee-rules`; efeitos percentuais ou descontos (pergunta 4).

## H. Urgência fixa e regras por clínica com condições (2026-11-15)

Decisões do usuário que ajustam a seção G:

- **Urgência = só valor fixo.** Sem dias da semana, horário nem texto de agenda. Só o **plantão**
  tem agenda (dias + horário, informativos). A migration `0043` remove `weekdays`, `start_time`,
  `end_time` e `schedule_label` de `urgency_fee_settings` (reversível: o downgrade recria as
  colunas vazias). A API recusa esses campos (`extra=forbid`, 422).
- **Regra por clínica = condições + valor fixo X.** `clinic_fee_rules.exam_ids` (UUID[]) e
  `attendance_types` (texto[]; `ROTINA`, `PLANTAO_NORMAL`, `PLANTAO_ESPECIAL`, `URGENTE`).
  - Lista vazia = qualquer. Dentro de uma lista basta um item (OU); as duas condições preenchidas
    valem juntas (E).
  - `ROTINA` = `service_level NORMAL`; `URGENTE` vem da marca de urgência (um atendimento de
    plantão urgente tem dois tipos).
  - A condição de exame olha os exames **ativos** do atendimento.
  - Várias regras da clínica que baterem **somam**, junto com plantão e urgência. Cada regra aplicada
    vira uma linha em `fee_lines` (nome da regra + valor).
  - Fora de escopo: condição por categoria, espécie, dia ou horário.
- **Quando recalcula:** ao confirmar e na prévia; ao corrigir tipo, urgência, clínica ou data
  (já era assim); e agora também ao **corrigir os exames** de um atendimento confirmado
  (`PUT /attendances/{id}/items`). Nesse caso só as linhas de clínica são reavaliadas; plantão e
  urgência ficam congelados como foram gravados. Editar uma regra depois nunca altera um
  atendimento que ninguém corrigiu.
- **Validação e auditoria:** exame inexistente ou tipo inválido = 422; criar e editar gravam
  `exam_ids` e `attendance_types` no antes/depois do `audit_log`; motivo obrigatório,
  `row_version` (409) e `Idempotency-Key` no POST continuam valendo. `Idempotency-Key` inclui as
  condições no hash do payload.
- **Limite conhecido:** o seletor de exames da condição lista os 100 primeiros exames do catálogo
  (página única da API); passar disso exige busca remota no seletor.
