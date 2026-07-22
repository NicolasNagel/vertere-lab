# Regras de Produto e Domínio
> Sem `paths:` — o glossário e a regra central valem para qualquer código que toque o domínio.

## Glossário (não traduza nem redefina)
- `Clinic` — clínica cliente do laboratório (o tenant).
- `Owner` — proprietário/tutor do animal. **Nunca chame de `Client`** quando houver ambiguidade
  entre clínica e tutor — essa confusão já é um dos problemas da planilha atual.
- `Patient` — o animal.
- `Veterinarian` — veterinário solicitante, vinculado a uma ou mais clínicas (N:N).
- `AttendanceRecord` — Registro de Atendimento, o agregado central.
- `AttendanceExam` — item de exame dentro de um atendimento (carrega o snapshot financeiro).
- `MonthlyClosure` — fechamento mensal por clínica e competência.
- `FinancialAdjustment` — ajuste posterior a um fechamento (append-only).
- `Report` — laudo (P1, ainda não implementado — mas já referencia `AttendanceRecord` por ID
  quando chegar a vez).

## Regra central
Toda funcionalidade futura referencia o `AttendanceRecord` **por ID** e respeita seus snapshots.
É proibido duplicar dado de atendimento em módulo paralelo sem vínculo explícito e justificativa
em ADR — é exatamente o tipo de duplicidade sem identificador estável que a planilha tinha
(`docs/01-analise-planilha.md` §2.1) e que este sistema existe para eliminar.

## O que uma história precisa ter para ser "pronta" (Definition of Ready)
Ator · permissão · escopo · pré-condições · fluxo · exceções · transições de estado · impacto
cadastral · impacto financeiro · impacto no fechamento · auditoria · critério de aceite. História
sem impacto declarado no Registro de Atendimento ou no fechamento não é aceita como prioridade do
núcleo (`docs/02-prd.md` §5, papel do Agente PO).

## Integridade histórica
- **Inative em vez de apagar** quando houver histórico associado — hard delete só é permitido
  para rascunho sem dependência.
- Preserve nome, código e preço **como estavam no momento do atendimento** — nunca sobrescreva
  silenciosamente com o dado cadastral atual.
- Preserve autor e data de toda mudança relevante.
- Merge de cadastro duplicado mantém os aliases antigos rastreáveis, não apaga a trilha.
- Fechamento sempre usa snapshot, nunca recalcula a partir do cadastro atual.

## Quando uma regra nova entra no domínio
- **Novo papel** exige matriz de permissão atualizada antes de ir a código.
- **Novo campo obrigatório** exige plano de backfill para dado já existente.
- **Novo valor financeiro** exige fórmula explícita e teste de reconciliação.
- **Novo estado** exige máquina de estado revisada e teste de transição (inclusive transição
  inválida).
- **Novo cadastro subsequente** (algo que a tela de atendimento cria "rápido") exige política de
  duplicidade própria antes de existir.
- **Nova forma de alterar dado pós-fechamento** exige política de ajuste — nunca implemente um
  atalho ad-hoc para "esse caso específico".