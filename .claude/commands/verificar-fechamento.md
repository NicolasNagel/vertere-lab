---
description: Verifica os invariantes de um MonthlyClosure já fechado (soma, unicidade, imutabilidade) contra o banco real.
argument-hint: "<closure_id | clinic_id + competencia>"
---
# /verificar-fechamento — auditoria pontual de um fechamento
Roda as checagens de integridade de um fechamento específico direto contra o banco — para
investigar suspeita de divergência ou para validar um fechamento antes de expor a exportação ao
financeiro. Complementa (não substitui) os testes automatizados de `13-monthly-closure.md`.

## Checagens
1. **Soma exata:** `SUM(monthly_closure_items.grand_total)` é idêntico a
   `monthly_closures.grand_total`? Divergência aqui é bloqueante e nunca deveria ter passado do
   commit original — se acontecer, é sinal de bug na transação de fechamento, não só do dado.
2. **Unicidade ativa:** existe mais de um fechamento com status ativo para o mesmo
   `(clinic_id, competence_year, competence_month)`? Deveria ser impossível pela constraint —
   se existir, a constraint está ausente ou foi contornada.
3. **Itens órfãos ou duplicados:** algum `AttendanceExam` está associado a mais de um fechamento
   ativo simultaneamente? Algum item elegível da competência ficou de fora sem estar em
   `ON_HOLD`/cancelado/motivo documentado?
4. **Imutabilidade:** algum item financeiro deste fechamento tem `updated_at` posterior ao
   `closed_at` do fechamento, sem estar associado a um `FinancialAdjustment`? Isso indica edição
   direta pós-fechamento — investigue o `audit_log` correspondente.
5. **Auditoria presente:** existe registro de `audit_log` para a criação, e para toda reabertura/
   ajuste subsequente, com autor e motivo preenchidos?
6. **Reabertura:** se houve reabertura, a versão anterior foi preservada (não sobrescrita)?

## Saída
```
# Verificação de fechamento — <closure_id> · <clinic> · <competência>
| Checagem | Resultado |
|---|---|
| Soma cabeçalho = soma itens | ✅/❌ (valores) |
| Unicidade ativa | ✅/❌ |
| Itens órfãos/duplicados | ✅/❌ (lista se houver) |
| Edição pós-fechamento sem ajuste | ✅/❌ (lista se houver) |
| Auditoria presente | ✅/❌ |
| Reabertura preserva versão anterior | ✅/❌/N-A |
**Veredito:** íntegro · divergência encontrada (bloqueante) · divergência com explicação
auditada (aceitável)
```

## Se encontrar divergência
Não corrija diretamente no banco. Reporte a divergência, a query usada para encontrá-la, e
recomende: (a) investigar a transação de fechamento original em busca de bug, ou (b) se for
edição indevida, tratar como incidente de segurança e acionar o `auditor-integridade`.