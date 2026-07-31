---
description: Testa de verdade (não simula) a feature recém-implementada — API real, navegador real, checklist de segurança do QA.
argument-hint: "<feature/rota tocada> [--seguranca-completa]"
---
# /testar-app — QA exploratório real
Roda depois de implementar uma feature/fatia (ver `/planejar-fatia`), antes de considerá-la
pronta. Usa a skill `qa-exploratorio` — **execute os passos de verdade contra o app rodando**;
não descreva o que "deveria" acontecer.

**Isto não depende de o usuário digitar `/testar-app`.** Toda feature nova ou refatoração exige
este QA como parte da Definição de Pronto (`.claude/rules/11-definition-of-done.md` item 14) — ao
terminar uma fatia e antes de reportá-la como concluída, rode isto proativamente, do mesmo jeito
que `/validar` já roda sem pedido explícito.

## 0. Suba e confirme o ambiente antes de testar
Não há `seed/gerar_dados_sinteticos.py` nem `docker-compose` neste repo — siga a seção "0. Suba
o ambiente de verdade" de `.claude/skills/qa-exploratorio/SKILL.md` (Postgres descartável via
`docker run`, migrations programáticas, `bootstrap_admin.py` para o primeiro usuário, papéis
extras via `UserModel` direto). Frontend só sobe se a feature tocar tela — **se não existir rota
ainda para a feature, declare isso e não force Playwright**. Falta algum pré-requisito? Diga isso
explicitamente e teste só o que der — não pule para "parece ok".

## 1. Identifique a superfície tocada
`git diff main...HEAD --stat` — quais endpoints, telas e módulos mudaram. Isso decide quais
itens da skill se aplicam (não rode a lista inteira em uma mudança de 3 linhas; não pule item
relevante numa mudança grande).

## 2. Funcional — bug hunting real
Siga a "Parte 1" de `.claude/skills/qa-exploratorio/SKILL.md`:
- Backend: `httpx` de verdade contra os endpoints tocados — caminho feliz (com dado real, não só
  sintético mínimo), borda, estado inválido, idempotência, **concorrência real via
  `asyncio.gather`** quando o endpoint criar/gravar algo a partir de um lote (escale a carga se um
  payload pequeno não abrir a janela de corrida), e **exaustão de recursos** (zip bomb/decompression
  bomb) em qualquer endpoint de upload. Depois de qualquer teste de escrita/concorrência, confira
  o estado direto no banco (`COUNT` vs `COUNT DISTINCT`), não só o corpo da resposta.
- Frontend (se tocou tela): Playwright de verdade — fluxo principal, os 5 estados obrigatórios
  (loading/erro/vazio/sucesso/desabilitado), teclado, duplo submit, console do navegador. Sem
  tela ainda para a feature? Declare isso e não force Playwright contra nada.

## 3. Segurança — sempre roda um subconjunto; `--seguranca-completa` roda os 13 itens
Por padrão, rode pelo menos os itens que qualquer alteração em `attendances`, `billing`,
`identity`, `owners`, `patients` ou `imports` sempre exige (ver `06-estrategia-qa.md §1` — são os
módulos de maior risco): IDOR/BOLA (`scripts/probe_idor.py`, sessão por cookie — login real, não
Bearer token), escalação vertical (em **cada** endpoint novo, não uma amostra), mass assignment,
excesso de campos em response, exaustão de recursos se houver upload. Com `--seguranca-completa`,
rode a tabela inteira dos 13 itens da SKILL.md, inclusive brute force, enumeração, CSRF, XSS
(`scripts/xss_payloads.txt`), SQL injection, PII em log, sessão após inativação.

## 4. Relatório (separe bug de vulnerabilidade)
```
# QA exploratório — <feature> · <data>
## Ambiente
Backend: rodando/não · Frontend: rodando/não · Banco: populado com N clínicas sintéticas
## Bugs funcionais encontrados
| # | O que testei | Comando/passo exato | Esperado | Observado | Severidade |
## Vulnerabilidades encontradas
| # | Item (1-13) | Script/passo exato | Esperado | Observado | Severidade | Bloqueia release? |
## Não testado (e por quê)
- item · motivo (ambiente indisponível, dado insuficiente, fora do escopo desta fatia)
## Veredito
aprovado · aprovado com ressalva · bloqueado (ver docs/06-estrategia-qa.md §12)
```

## 5. Encaminhamento
Achou vulnerabilidade crítica/alta ou vazamento entre clínicas? Isso bloqueia release por
definição (`06-estrategia-qa.md §12`) — recomende rodar também `auditor-integridade` antes de
qualquer merge. Achou bug funcional sem risco de segurança? Corrija, reexecute o mesmo
comando/script para confirmar "antes vs. depois", e rode `/validar` de novo. Em qualquer caso,
feche o ambiente (seção "Encerramento" da SKILL.md) antes de reportar a fatia como concluída —
processo/container/arquivo de teste não pode sobreviver à sessão.

## Honestidade
Item não testado é lacuna declarada, nunca "provavelmente está ok". Resultado sem comando/passo
reprodutível anexado não conta como teste — é suspeita, marque como tal.