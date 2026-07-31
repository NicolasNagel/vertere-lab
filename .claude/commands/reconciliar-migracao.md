---
description: Reconcilia um lote de importação da planilha contra os critérios de aceite do docs/01-analise-planilha.md §5.
argument-hint: "<import_batch_id> [--dry-run]"
---
# /reconciliar-migracao — verificação de lote de importação
Confronta um `import_batch_id` com os critérios de aceite formais da migração. Existe porque a
migração é um evento de alto risco e único — errar a reconciliação aqui vira dívida financeira
não descoberta, exatamente o problema que este projeto existe para resolver
(`docs/01-analise-planilha.md`).

## Números de referência (não são estimativa — são o alvo a bater)
- **1.794 registros operacionais válidos.**
- **Soma financeira: R$ 185.017,00.**
- Diferença conhecida de R$ 100,00 vem de um valor residual sem atendimento — **não deve** ter
  sido importado como item financeiro.

## Passos
1. **Contagem de status:** toda linha do lote (`ImportRow`) tem estado final? Liste quantas
   estão em cada status; qualquer linha sem estado final é bloqueante.
2. **Soma financeira:** some o `grand_total` de todos os `AttendanceRecord` criados por este
   lote. Bate com R$ 185.017,00? Se não, a diferença precisa estar 100% explicada por exceção
   aprovada — não por arredondamento silencioso.
3. **Unicidade de protocolo:** nenhum `protocol_number` duplicado no lote nem colidindo com dado
   já existente.
4. **Cadastro sem aprovação:** nenhuma `Clinic`/`Veterinarian`/`Owner`/`Patient` foi criada por
   aproximação automática sem estar no mapa de alias aprovado — liste qualquer criação fora
   desse mapa como achado.
5. **Valor residual:** confirme que a linha com valor sem atendimento associado foi reportada
   como exceção e **não** virou item financeiro.
6. **Idempotência:** se `--dry-run` não foi passado, confirme que reprocessar este mesmo lote
   não duplicaria dado (rode a consulta de detecção de duplicata do módulo de import).

## Saída
```
# Reconciliação — lote <import_batch_id> · <data>
| Critério | Esperado | Encontrado | Status |
|---|---|---|---|
| Linhas com estado final | 100% | ... | ✅/❌ |
| Soma financeira | R$ 185.017,00 | R$ ... | ✅/❌ |
| Protocolos únicos | sim | ... | ✅/❌ |
| Cadastro fora do alias aprovado | 0 | ... | ✅/❌ |
| Valor residual sem atendimento importado | 0 | ... | ✅/❌ |
**Veredito:** aprovado para corte · aprovado com exceção documentada · bloqueado
**Divergências:** cada uma com a query usada para encontrar e a ação recomendada (exceção
formal, correção de alias, ou reprocessamento).
```

## Honestidade
Divergência sem explicação nunca é "provavelmente arredondamento" — é bloqueante até virar
exceção formal aprovada por humano, conforme `.claude/rules/10-data-migration.md`.