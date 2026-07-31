---
# Regras de Redis e jobs — carrega ao tocar infra de cache/fila/worker (opcional na V1).
paths:
  - "backend/app/shared/infrastructure/**/redis*.py"
  - "backend/app/shared/infrastructure/**/queue*.py"
  - "backend/app/shared/infrastructure/**/cache*.py"
  - "backend/workers/**"
---
# Regras de Redis e Jobs Python

## Antes de introduzir Redis
Redis **não é obrigatório** para o núcleo da V1. Só adicione depois de medir uma necessidade real
(rate limit distribuído, cache com hipótese testada, lock não coberto por PostgreSQL, fila com
worker externo) — nunca "porque pode ser útil depois" (viola YAGNI do `AGENTS.md`).

## Regras quando existir
- **Nunca é fonte de verdade** — atendimento, preço, fechamento, permissão e laudo nunca vivem
  só no Redis.
- Chave segue o padrão `<env>:vertere:<escopo>:<domínio>:v<versão>:<key>`.
- Cache sempre com TTL; payload mínimo, sem PII desnecessária.
- Invalidação definida **junto** da escrita que a torna necessária, não depois.
- Cache miss precisa funcionar corretamente (Redis fora do ar não pode quebrar o fluxo).
- Falha de Redis **nunca** corrompe atendimento ou fechamento — esses fluxos são garantidos pelo
  PostgreSQL, Redis é só otimização.

## Locks
- Prefira lock do PostgreSQL para integridade real; lock Redis só para coordenação distribuída
  não-transacional.
- Lock tem TTL e token de propriedade; só o dono libera.
- Lock Redis **não substitui** unique constraint no banco.

## Jobs (quando houver worker externo)
Biblioteca aprovada por ADR, sem misturar framework de fila no meio do caminho. Todo job tem:
nome estável, payload versionado com schema Pydantic, idempotency key, correlation ID, escopo,
retry com backoff, timeout, dead-letter, log/métrica, handler pequeno, e **teste de
reprocessamento** (rodar o job duas vezes não pode duplicar efeito).

## Vercel
- Nunca inicie worker dentro do FastAPI rodando na Vercel.
- `BackgroundTasks` do FastAPI **não é garantia de job durável** — não trate como fila.
- Cron não substitui fila para efeito crítico sem desenho de idempotência.
- Job longo roda em serviço externo; outbox no PostgreSQL preserva a intenção até um worker
  processar.

## Prioridade futura (quando isso for implementado)
Geração de PDF de laudo → entrega de laudo → notificações → exportação grande → importação →
comunicação 1:N. Nenhum desses é P0 — ver ordem proibida no `AGENTS.md`.