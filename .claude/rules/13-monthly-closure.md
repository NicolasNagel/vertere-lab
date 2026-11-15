---
# Regras do fechamento mensal — carrega ao tocar o módulo de billing/fechamento.
paths:
  - "backend/app/modules/billing/**"
  - "frontend/src/features/billing/**"
---
# Regras Específicas do Fechamento Mensal

## Fonte
Fechamento consome **só** item de atendimento persistido e elegível. É proibido inserir valor
manual sem passar por uma entidade de ajuste (`FinancialAdjustment`) — nunca um `UPDATE` direto
"pra bater a conta".

## Prévia
Não fecha nem bloqueia nada — é só leitura. Usa **a mesma regra de elegibilidade** do fechamento
de verdade (nunca uma versão simplificada que depois diverge). Mostra item elegível e item
bloqueado com motivo. Totais calculados no backend. Pode ficar desatualizada por mudança
concorrente — não é documento contábil final, é preview.

## Período
Fechamento é por **período livre** (`period_start`/`period_end`), não só mês calendário —
clínicas com fechamento quinzenal escolhem qualquer intervalo. Elegibilidade decide por
`service_date` do atendimento dentro do período, nunca por `billing_competence` (esse campo
continua imutável e gravado na confirmação, só deixou de ser o critério de seleção do
fechamento — `.claude/rules/03-database.md`).

## Fechar
Pré-condição: permissão `closures.close` · clínica elegível · período válido (`period_end >=
period_start`) · nenhuma inconsistência bloqueante · nenhum outro fechamento ativo cujo período
se sobreponha ao selecionado para essa clínica · `Idempotency-Key`.

Fluxo transacional único: advisory lock por clínica → revalida inexistência de fechamento ativo
com período sobreposto → seleciona e bloqueia os itens elegíveis → **recalcula totais no backend**
(nunca confia na prévia antiga) → cria fechamento + snapshots → associa os itens fonte → compara
soma dos snapshots com o cabeçalho **antes do commit** → grava auditoria e outbox → commit.
Nenhuma exportação ou envio externo acontece dentro dessa transação.

## Imutabilidade
Fechamento `CLOSED` não é editado. Atendimento associado a um fechamento fechado só muda
financeiramente pelo caso de uso de correção (`attendances.application.closure_settlement`), que
grava o ajuste correspondente no próprio fechamento. Ajuste é entidade **append-only**. Reabertura é
excepcional e preserva a versão anterior (nunca sobrescreve). Motivo e autor são obrigatórios em
qualquer uma dessas exceções. Exportação sempre parte do snapshot + ajustes, nunca recalcula do
atendimento vivo.

## Ajuste
Referencia o fechamento e, quando possível, o item original. Tipo é crédito ou débito explícito;
tem valor, motivo, autor e data. **Não modifica o snapshot original** — aparece como camada
adicional em exportação e versão posterior.

## Reabertura
Excepcional por definição: permissão específica · reautenticação quando a política adotar
step-up · justificativa obrigatória · auditoria · lock contra reabertura concorrente ·
preservação da versão anterior · nova versão `CLOSED` quando fechar de novo.

## Retroatividade
Período já fechado **não recebe atendimento silenciosamente**. A política escolhe entre ajuste
no período atual ou reabertura formal — a decisão fica auditada, nunca é implícita no código.
Competência de um atendimento não muda sem um caso de uso específico e auditado para isso.

## Endpoints (docs/07-nucleo-v1.md §4.6)
```
GET  /api/v1/closures/preview?clinic_id=&period_start=&period_end=
POST /api/v1/closures                 { clinic_id, period_start, period_end }
GET  /api/v1/closures
GET  /api/v1/closures/{id}
GET  /api/v1/closures/by-period?clinic_id=&period_start=&period_end=
POST /api/v1/closures/{id}/adjustments
POST /api/v1/closures/{id}/reopen
GET  /api/v1/closures/{id}/export
```

## Testes obrigatórios (além dos gates gerais em 08-testing.md)
Dois fechamentos simultâneos para a mesma clínica com período sobreposto · dois fechamentos para
a mesma clínica com períodos livres não sobrepostos (ambos devem passar — é o caso quinzenal) ·
mesma idempotency key repetida · mesma key com payload diferente (deve dar conflito) · item já
pertencente a outro fechamento · soma exata cabeçalho vs. itens · item cancelado excluído
corretamente · ajuste sem apagar original · reabertura sem permissão (deve bloquear) ·
exportação fiel ao snapshot · falha antes do commit não deixa estado parcial no banco.
