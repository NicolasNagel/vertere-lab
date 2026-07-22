# Definição de Pronto (DoD)
> Sem `paths:` — vale para toda entrega. Extraída de `docs/05-roadmap-backlog.md` §11.
> Uma tarefa só é dada como pronta quando **todos** os itens aplicáveis passam de verdade —
> "declarar concluído sem ter executado a validação" é proibição explícita do `CLAUDE.md`.

1. **Implementação completa** — cobre o que a história/issue pediu, não uma fração.
2. **Ruff passa** (lint + format check).
3. **mypy passa** no escopo definido (estrito em `domain`/`application`).
4. **TypeScript passa** (`strict: true`, zero `any` novo).
5. **Testes unitários e de integração passam** — integração usa PostgreSQL real, não mock de
   toda a persistência (`09-testing.md`).
6. **E2E crítico passa** quando o fluxo tocado tem cenário E2E definido em `docs/06-estrategia-qa.md`.
7. **Migration revisada e aplicada em ambiente de teste** — autogerada sempre revisada à mão,
   nunca aceita como veio.
8. **Autorização testada no backend** — nunca "a UI já esconde o botão".
9. **Auditoria verificada** — se a ação é crítica (ver lista no `CLAUDE.md`), o `audit_log` foi
   gravado e o teste confirma isso.
10. **Logs e métricas adequados** quando a mudança afeta um fluxo observado.
11. **Nenhum segredo ou PII indevida** em código, log ou teste.
12. **Rollback considerado** — migration reversível ou plano de restauração documentado.
13. **Critérios de aceite demonstrados**, não assumidos.

Item que não pôde ser executado nesta sessão (ex.: sem acesso a banco de teste) deve ser
declarado explicitamente como pendente — nunca reportado como se tivesse passado.