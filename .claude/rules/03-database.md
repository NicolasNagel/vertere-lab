---
# Regras de banco — carrega ao tocar modelos ORM, infraestrutura de persistência ou migrations.
paths:
  - "backend/app/**/models.py"
  - "backend/app/shared/infrastructure/**/*.py"
  - "backend/alembic/**"
---
# Regras de PostgreSQL, SQLAlchemy e Alembic

## Modelagem
- Tabela em `snake_case`; PK opaca; FK obrigatória para toda relação real.
- `NUMERIC` para dinheiro, `TIMESTAMPTZ` para instante, `DATE` para data civil.
- `JSONB` só para metadado variável ou snapshot deliberado — não para modelar relação que devia
  ser tabela.
- Constraint expressa invariante (não é só documentação): nome explícito em toda constraint e
  índice.

## SQLAlchemy
- Modelo ORM é separado da entidade de domínio — **não é Active Record**.
- Relação não deve causar carregamento inesperado na serialização (lazy load vazando pro
  response).
- Repository controla a query; unit of work controla commit/rollback.
- Nunca retorne objeto lazy após a sessão ter fechado. Mapeie `Decimal` e enum explicitamente.

## Alembic
- Migration autogerada **sempre revisada à mão** antes de aceitar.
- Uma mudança coerente por migration; nunca edite migration já aplicada — nova migration corrige.
- Coluna obrigatória em tabela já populada não nasce `NOT NULL` direto: **expand → backfill →
  contract**.
- Índice e constraint com nome explícito; migration não importa código de aplicação instável.
- Teste `upgrade` em banco vazio **e** em banco com dado representativo.
- `downgrade` quando seguro; quando não for seguro, documente o procedimento de restauração
  operacional em vez de fingir que existe um downgrade automático.

## Multi-tenant e escopo
- Tabela ligada a clínica carrega `clinic_id`; unique local inclui `clinic_id` (evita colisão
  entre tenants diferentes).
- Índice de busca por tenant começa por `clinic_id` quando isso reflete o padrão de consulta real.
- Consulta sem escopo só existe em repositório global explicitamente autorizado — não é o padrão.
- Seed e migration **nunca vazam dado entre escopos** (isso vale também para dado de teste, ver
  `08-testing.md` e `10-data-migration.md`).

## Concorrência
- Sequência de protocolo em tabela própria (`attendance_sequences`) ou sequence nativa aprovada
  em ADR. **`MAX + 1` é proibido** — é a causa raiz do bug de protocolo da planilha atual.
- Fechamento usa advisory lock transacional (ou mecanismo PostgreSQL equivalente) por clínica +
  competência.
- Edição crítica usa versão (row version); transação com isolamento consciente, nunca aberta
  durante chamada externa.

## Fechamento (invariantes de banco)
- Unique ativo por `(clinic_id, competence_year, competence_month)`.
- Item fonte associado a **no máximo um** fechamento ativo por vez.
- Snapshot contém valor suficiente para reprodução total sem consultar o atendimento original.
- Soma dos itens verificada contra o cabeçalho **antes do commit**, não depois.
- Reabertura preserva a versão anterior; ajuste é append-only.

## Índices
- Criados a partir de consulta real, não por precaução; valide `EXPLAIN (ANALYZE, BUFFERS)` em
  staging antes de assumir que o índice ajuda.
- Evite índice redundante — cada índice tem custo de escrita.

## Backup
- Backup automático + PITR quando disponível; restore **testado**, não assumido.
- Credencial de runtime com privilégio mínimo; credencial de migration separada quando possível.
