---
description: Fecha a sessão de trabalho — atualiza o HANDOFF.md com estado real (git), pendências e armadilhas.
argument-hint: "[--issue <N>]"
---
# /handoff — passagem de bastão
Atualize o `HANDOFF.md` da raiz para que **a próxima sessão (ou outra pessoa) continue sem
arqueologia**. É o item 10 da [Definição de Pronto](../rules/definicao-de-pronto.md). Fonte da
verdade = git + estado do gate; a conversa só complementa.

## 1. Colete o estado real
- `git status` e `git diff --stat` — o que está commitado vs. pendente.
- `git log --oneline -10` — o que foi entregue nesta sessão.
- Último resultado do gate (`/validar`): verde ou vermelho, e onde falha.
- Vereditos de `revisor-codigo` / `auditor-seguranca` emitidos na sessão, se houver.

## 2. Sobrescreva o `HANDOFF.md` neste formato
```
# Handoff — <data> · Fase <N> do roadmap · issue #<N>
## Feito nesta sessão
- bullets curtos, um por entrega real (com commit/arquivo quando ajudar)
## Estado do gate
- backend: verde/vermelho (se vermelho: qual check e onde) · frontend: idem · migrações: head?
## Em andamento (não finalizado)
- o que ficou pela metade, em qual arquivo, e qual era o plano
## Armadilhas conhecidas
- comportamentos não óbvios descobertos na sessão (ex.: "webhook da Meta reenvia após 7s",
  "constraint de exclusão exige extensão btree_gist")
## Próximo passo recomendado
- 1–3 bullets acionáveis, em ordem
## Pendências fora do código
- decisão esperando ADR, dado faltando, dependência externa (ex.: template Meta em aprovação)
```

## Antes de escrever o handoff — registre a entrega
Se esta sessão fechou uma issue, rode primeiro (evita que `metrics/entregas.jsonl` fique
esquecido — ver `scripts/registrar_entrega.py`):
```bash
uv run scripts/registrar_entrega.py --issue <N> --fase <N> --fluxo <fluxo|none> \
  --revisor <veredito> --auditor <veredito> --gate-tentativas <N> --autonoma <true|false>
```
Preencha `--revisor`/`--auditor` com o veredito real que os subagentes deram nesta sessão — não
adivinhe; se não rodaram, use `nao_rodou`.

## 3. Regras de honestidade
- **Não embeleze:** gate vermelho entra como vermelho; tarefa 80% pronta entra como
  "em andamento", nunca em "Feito".
- **Nada de segredo ou PII** no handoff (é um arquivo versionado).
- Se a sessão não mudou nada relevante, diga isso em uma linha — handoff vazio honesto vale
  mais que um inflado.