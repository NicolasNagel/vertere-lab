# Definição de Pronto (DoD)
> Sem `paths:` — vale para toda entrega. Extraída de `docs/05-roadmap-backlog.md` §11.
> Uma tarefa só é dada como pronta quando **todos** os itens aplicáveis passam de verdade —
> "declarar concluído sem ter executado a validação" é proibição explícita do `AGENTS.md`.

1. **Implementação completa** — cobre o que a história/issue pediu, não uma fração.
2. **Ruff passa** (lint + format check).
3. **mypy passa** no escopo definido (estrito em `domain`/`application`).
4. **TypeScript passa** (`strict: true`, zero `any` novo).
5. **Testes unitários e de integração passam** — integração usa PostgreSQL real, não mock de
   toda a persistência (`08-testing.md`).
6. **E2E crítico passa** quando o fluxo tocado tem cenário E2E definido em `docs/06-estrategia-qa.md`.
7. **Migration revisada e aplicada em ambiente de teste** — autogerada sempre revisada à mão,
   nunca aceita como veio.
8. **Autorização testada no backend** — nunca "a UI já esconde o botão".
9. **Auditoria verificada** — se a ação é crítica (ver lista no `AGENTS.md`), o `audit_log` foi
   gravado e o teste confirma isso.
10. **Logs e métricas adequados** quando a mudança afeta um fluxo observado.
11. **Nenhum segredo ou PII indevida** em código, log ou teste.
12. **Rollback considerado** — migration reversível ou plano de restauração documentado.
13. **Critérios de aceite demonstrados**, não assumidos.
14. **QA exploratório real** (skill `qa-exploratorio`) em **toda feature nova ou refatoração**,
    não só nos módulos de maior risco — execução real contra o app rodando, não descrição do que
    "deveria" funcionar. **Roda automaticamente, sem o usuário precisar digitar `/testar-app`** —
    é parte do critério de conclusão da tarefa, do mesmo jeito que Ruff/mypy/testes rodam sem
    pedido explícito. Achado de segurança crítico/alto bloqueia conforme
    `docs/06-estrategia-qa.md §12`.

15. **QA independente aprovou** — subagente `qa-fatia` conferiu cada critério de aceite do plano
    contra o app rodando e devolveu evidência por critério (não "parece certo"). Ele executa a
    skill `qa-exploratorio`, então este item é a forma de cumprir o item 14.
16. **Revisão independente aprovou** — subagente `revisor-codigo` (e `auditor-integridade` quando
    há dinheiro, permissão, tenant, atendimento, fechamento, importação ou identidade) confrontou
    o diff com o plano e as rules. Achado bloqueante corrigido; ressalva registrada com dono.
17. **Commit feito** — a fatia termina em commit coerente em branch própria (nunca na `main`),
    com mensagem que cita critérios atendidos e o resultado de gates, QA e revisão. Alteração sem
    commit não está pronta, por mais verde que esteja (fluxo completo no `AGENTS.md`).

Item que não pôde ser executado nesta sessão (ex.: sem acesso a banco de teste) deve ser
declarado explicitamente como pendente — nunca reportado como se tivesse passado.