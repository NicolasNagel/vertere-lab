---
# Regras de backend — carrega ao tocar código Python do app.
paths:
  - "backend/app/**/*.py"
---
# Regras de Backend — FastAPI

## Routers
- Router só valida protocolo HTTP e delega — **sem SQL, sem regra de negócio**.
- `APIRouter` por módulo, prefixo `/api/v1`.
- Dependências explícitas para sessão, usuário, autorização e unit of work.
- `response_model` sempre definido; status HTTP correto; paginação obrigatória em listas.

## Pydantic
- Schemas de `create`, `update`, `read` e `filter` **separados** — nunca reutilize modelo ORM
  como schema de resposta.
- `extra='forbid'` em entrada sensível (evita mass assignment).
- Serializer não executa consulta; não exponha campo interno por acidente.

## Casos de uso (application)
- Uma classe/função por intenção de negócio; recebe dependência por construtor.
- Controla transação via **unit of work**; autorização contextual acontece antes do efeito.
- Retorna DTO de aplicação, nunca objeto ORM; nunca chama FastAPI diretamente (domínio não
  conhece a camada de apresentação).

## Repositories
- Interface em `application`/`domain`; implementação em `infrastructure`.
- Repository **não chama `commit`** — quem decide é o unit of work.
- Query sempre explícita, paginada, e aplica o escopo de clínica. Evite N+1; use eager loading
  só quando necessário e medido.

## SQLAlchemy (uso no backend — modelagem fica em `04-database.md`)
- Sessão por request/caso de uso — **nunca sessão global**, nunca compartilhada entre tarefas.
- Transação curta; mapeie `IntegrityError` para conflito de domínio (não deixe vazar como 500).
- Use `select()` moderno (2.x), não a API legada.

## Autorização
- Permissão e escopo checados no backend, antes da consulta quando possível.
- `404` pode (e deve, quando fizer sentido) ocultar recurso de outro escopo — não vaze
  existência de dado de outra clínica.
- Usuário interno com escopo global precisa de permissão explícita, nunca implícita por ser
  "admin de alguma coisa".
- Negação relevante gera log seguro (sem PII no log).

## Idempotência
- `POST` de criação/confirmação/fechamento aceita `Idempotency-Key`.
- Chave vinculada a ator + escopo + operação + hash do payload.
- Mesma chave + mesmo payload → retorna o resultado anterior. Mesma chave + payload diferente →
  `409`. Registro persistido no PostgreSQL (não em Redis/memória).

## Concorrência
- Row version (ou `updated_at` comparado de forma aprovada) para edição concorrente; conflito
  retorna `409`.
- Sequência de protocolo e fechamento usam lock do PostgreSQL — nunca lock Redis para substituir
  constraint.
- Todo fluxo com concorrência real ganha teste de concorrência real (ver `09-testing.md`).

## Códigos de erro mínimos
`UNAUTHENTICATED` · `FORBIDDEN` · `NOT_FOUND` · `VALIDATION_ERROR` · `CONFLICT` ·
`INVALID_STATE_TRANSITION` · `IDEMPOTENCY_CONFLICT` · `ATTENDANCE_ALREADY_CLOSED` ·
`CLOSURE_ALREADY_EXISTS` · `PRICE_NOT_AVAILABLE` · `EXTERNAL_SERVICE_UNAVAILABLE` ·
`INTERNAL_ERROR`.

## Performance
- Endpoint comum não executa trabalho pesado; exportação grande é assíncrona quando necessário.
- Selecione só o campo usado; meça query count nos fluxos críticos (atendimento, fechamento).
- Cache só depois de medir — nunca cache especulativo.