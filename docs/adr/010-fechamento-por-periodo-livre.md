# ADR-010 — Fechamento por período livre com nome histórico `MonthlyClosure`

- **Status**: aceita
- **Data**: 2026-08-09

## Contexto

Algumas clínicas fecham quinzenalmente ou em intervalos que não coincidem com o mês civil. A
unicidade anterior por `(clinic_id, competence_year, competence_month)` impedia dois períodos
não sobrepostos no mesmo mês e não representava a invariante real.

O domínio e as tabelas já usam os nomes públicos `MonthlyClosure`, `monthly_closures` e
`monthly_closure_items`. Renomeá-los agora ampliaria o risco de compatibilidade sem melhorar a
integridade do fluxo.

## Decisão

O fechamento aceita um intervalo inclusivo definido por `period_start` e `period_end`, com
`period_end >= period_start`. A elegibilidade usa `AttendanceRecord.service_date` dentro desse
intervalo. `billing_competence` não participa da seleção.

Para uma mesma clínica, fechamentos em estado `CLOSED` não podem ter períodos sobrepostos. A
invariante é garantida no PostgreSQL por uma exclusion constraint GiST sobre `clinic_id` e
`daterange(period_start, period_end, '[]')`, além do advisory lock transacional por clínica.
Períodos não sobrepostos — inclusive duas quinzenas no mesmo mês — são permitidos.

Os nomes `MonthlyClosure` e `monthly_closures` permanecem por compatibilidade histórica e passam
a significar fechamento por período. `competence_year` e `competence_month` permanecem como
metadados legados derivados de `period_start`; não são chave de unicidade nem critério de
elegibilidade. Contratos novos usam `period_start` e `period_end` como entrada.

## Consequências

- Reabertura muda o estado para `REOPENED` e libera o intervalo para um novo fechamento, sem
  apagar o snapshot anterior.
- Idempotência continua vinculada ao payload completo, incluindo as duas extremidades.
- Prévia, fechamento, consulta por período e interface usam o mesmo intervalo inclusivo.
- Exportações e leituras preservam os campos históricos enquanto houver consumidores antigos.
- Uma futura remoção ou renomeação de `MonthlyClosure` e dos campos `competence_*` exige migration
  e política de depreciação próprias; não faz parte desta remediação.

## Rollback

A migration pode restaurar o índice parcial por competência, mas isso só é seguro se não houver
mais de um fechamento `CLOSED` com o mesmo `competence_year`/`competence_month`. Antes do
downgrade, a operação deve consultar e reconciliar esses conflitos; a extensão `btree_gist`
permanece instalada porque pode ser compartilhada por outros objetos.
