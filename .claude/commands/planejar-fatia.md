---
description: Quebra uma feature/issue em fatias verticais pequenas com checkpoint de aprovação, antes de escrever qualquer código.
argument-hint: "<descrição da feature ou número da issue>"
---
# /planejar-fatia — plano de fatias verticais
Antes de codificar qualquer coisa não trivial, produza um plano de fatias pequenas e pare para
aprovação. Existe porque "fatia vertical" (docs/05-roadmap-backlog.md §1) era só um princípio de
roadmap — este command o transforma em passo obrigatório de toda tarefa de porte médio/grande.

## Quando usar
Sempre que a tarefa não couber confortavelmente num único commit revisável (~1 caso de uso, ~1
migration, ~1 conjunto pequeno de testes). Tarefa de uma linha ou correção pontual não precisa
disso — não burocratize o trivial.

## Como planejar
1. **Localize a fase do roadmap** (`docs/05-roadmap-backlog.md`) que a feature pertence — não
   aceite trabalho fora da ordem de prioridade do `AGENTS.md` sem sinalizar isso explicitamente.
2. **Releia o gate da fase** — a lista de "Gate:" daquela fase é o critério de "fatia terminou
   de verdade", não só "compilou".
3. **Quebre em fatias na ordem de dependência real**, cada uma:
   - pequena o bastante para revisar em poucos minutos;
   - termina em estado consistente (nunca deixa código quebrado entre fatias);
   - tem teste próprio, não empresta teste da fatia seguinte;
   - referencia o(s) arquivo(s) que serão tocados.
4. **Não esconda risco dentro de uma fatia genérica** — se uma fatia mexe em dinheiro,
   concorrência, autorização ou fechamento, ela é a fatia dela sozinha, não um item dentro de
   "implementar endpoint".

## Saída (pare aqui e espere confirmação — não comece a codificar)