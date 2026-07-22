---
# Regras de migração — carrega ao tocar o módulo de importação ou o seed da planilha.
paths:
  - "backend/app/modules/imports/**"
  - "seed/**"
  - "docs/migration/**"
---
# Regras de Migração da Planilha

## Princípios
Preservar a origem · staging imutável · importação idempotente · nenhum merge incerto automático
· toda linha recebe um status final · reconciliação antes de qualquer corte · rastreabilidade por
lote e por linha (`import_batch_id` + `source_row_number`).

## Fluxo (docs/01-analise-planilha.md §4)
1. congelar cópia da planilha de origem;
2. checksum do arquivo congelado;
3. carregar em staging **sem transformar** o conteúdo original;
4. guardar número da linha e conteúdo bruto;
5. normalizar (clínica, veterinário/CRMV, proprietário, exame);
6. aplicar mapa de aliases **aprovado por humano**, nunca fuzzy match silencioso;
7. detectar duplicidade provável e reportar, não decidir sozinho;
8. mapear para catálogo de exame e preço vigente na época;
9. gerar relatório de exceções para todo caso ambíguo;
10. rodar em **dry-run** primeiro;
11. reconciliar contagem e valor contra os números validados abaixo;
12. aprovação humana das exceções;
13. importar de forma definitiva e idempotente (reprocessar não duplica);
14. emitir relatório final.

## Números de referência para reconciliação (não são estimativa — são o alvo)
- **1.794 registros operacionais válidos.**
- **Soma financeira validada: R$ 185.017,00** (não R$ 185.117,00 — a diferença de R$ 100,00 é um
  valor residual sem atendimento e **não deve ser importado como item financeiro**).
- Protocolos devem ser únicos após a importação.
- 100% das linhas — válidas ou não — têm estado final conhecido (importada, exceção resolvida,
  ou rejeitada com motivo).

## Registro de Atendimento migrado
- Cada linha válida vira uma entidade rastreável até a linha de origem.
- Protocolo legado é preservado como referência, não descartado.
- Valor residual sem atendimento associado **nunca** vira item financeiro (é exatamente o bug
  que causou a divergência de R$ 100,00 na planilha atual).
- Preço da linha legada vira snapshot imutável, não referência viva ao catálogo atual.
- Ausência de dado permitida pela regra clínica registra motivo e o usuário/processo responsável.
- Cadastro é deduplicado por regra aprovada (alias mapeado), nunca por aproximação automática
  silenciosa — toda deduplicação incerta vira exceção para aprovação humana.

## Fechamento de dado migrado
- Dado migrado entra com competência financeira definida explicitamente, não inferida.
- Fechamento histórico só é criado **depois** da reconciliação completa.
- Soma dos itens migrados bate com a soma validada; toda diferença exige exceção formal aprovada,
  nunca um ajuste silencioso "pra fechar a conta".
- Importação **nunca** marca um período como fechado sem aprovação humana explícita.

## Critério de aceite da migração (docs/01-analise-planilha.md §5)
A migração só é aceita quando: 100% das linhas válidas têm estado final conhecido · a soma
financeira importada corresponde a R$ 185.017,00 (salvo ajuste aprovado e documentado) · nenhuma
clínica/veterinário foi criado silenciosamente por aproximação incerta · todo conflito está no
relatório de exceções · protocolos são únicos · relatório de duplicidade e de campo ausente foi
entregue · o lote pode ser reprocessado sem duplicar dado.