# Regras Globais de Código
> Sem `paths:` — vale para todo arquivo do repositório, backend e frontend.

## Linguagem
- Código, identificadores e commits em **inglês**; documentação de produto pode estar em
  português (como está em `docs/`).
- Nomes refletem o domínio (`AttendanceRecord`, `MonthlyClosure`, não `Record`/`Closure` genérico).
- Comentário explica **decisão**, não o óbvio. Evite abreviação não aprovada pelo time.

## Python
- Python 3.12+; type hints em toda função pública e método relevante.
- `from __future__ import annotations` quando útil.
- Ruff para lint e format; **mypy estrito** nos módulos `domain` e `application` (infra pode ser
  mais permissivo, mas não solto).
- **Proibir `Any` por padrão** — prefira `Protocol`, generics, tipos concretos.
- Value objects/dataclasses **imutáveis** quando apropriado; nunca mutable default argument.
- Exceção genérica não é fluxo normal — nunca `except Exception: pass`.
- Funções pequenas, responsabilidade única; composição em vez de herança profunda (ver
  "Princípios de código" no `CLAUDE.md` e "Classe ou função?" logo abaixo dessa seção).
- **Dependency Inversion na prática, não só no nome**: módulo de alto nível (`application`)
  depende de interface, nunca de implementação concreta de `infrastructure` — é por isso que
  repositório é sempre interface + implementação separadas (`03-backend.md`), não um detalhe de
  organização de pasta.
- Patterns (Factory, Strategy, Specification, etc.) são situacionais, não meta de "código
  profissional" — gatilho de quando usar cada um está em `03-backend.md`, seção "Patterns
  aprovados". Sem gatilho real, é função simples.

## TypeScript
- `strict: true`; proibir `any` por padrão — use `unknown` + narrowing.
- Nunca `as` para esconder erro de tipo.
- Contratos da API tipados explicitamente (ou gerados) — componente não conhece detalhe de
  persistência.

## Erros
- Exceção de domínio tem **código estável** (ver lista em `02-backend.md`); a camada de
  apresentação converte para HTTP, nunca expõe stack trace ao cliente.
- Erro esperado não é `500`. Logue a causa com segurança (sem PII/segredo).
- Preserve a cadeia: `raise NovoErro(...) from exc`.

## Datas
- Instante em **UTC** e `TIMESTAMPTZ`; nunca depender do timezone implícito do servidor.
- `service_date` (data do atendimento) e `billing_competence` (competência financeira) são
  campos explícitos e distintos — não derive um do outro por acaso.
- Frontend apresenta em `pt-BR` com o timezone configurado; testes usam relógio controlável.

## Dinheiro
- Python `Decimal`; PostgreSQL `NUMERIC(14,2)`. **Nunca `float`.**
- Arredondamento centralizado em um único lugar do domínio; moeda explícita.
- Total sempre calculado no backend, nunca confiado do frontend.
- Compare `Decimal`, nunca string formatada.

## IDs
- PK opaca (UUID/ULID conforme ADR); protocolo de negócio (`protocol_number`) é campo separado
  da PK, nunca a mesma coisa.
- FK verdadeira sempre que houver relação — nunca ID solto em JSON/CSV sem justificativa.
- ID nunca é mecanismo de autorização (posse do ID ≠ permissão de acesso).

## Dependências
- Não misture gerenciador de dependência (um só por stack).
- Antes de adicionar lib: avalie licença, manutenção, superfície de risco; não adicione biblioteca
  para função trivial que a stdlib/stack já resolve.
- Remova dependência sem uso.

## Git
- Commits pequenos e coerentes; migration acompanha o código na mesma mudança.
- Nunca commitar segredo, dump de banco ou dado real.
- Não reformate arquivo não relacionado à mudança; não altere contrato público sem documentar.