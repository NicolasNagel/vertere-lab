# ADR-012 — Redesign do frontend para visual ERP denso e neutro

## Status

Proposto — 2026-11-14. Passa a Aceito quando a paleta e a fonte do passo B0.3 forem aprovadas.

## Contexto

O frontend segue os mockups de `assets/features/screens/` (visual editorial: creme, títulos em
Big Shoulders, espaçamento generoso). O produto é uma ferramenta operacional usada o dia inteiro
pela recepção e pelo financeiro: precisa de densidade, tabelas legíveis e aparência neutra de ERP.
`.claude/rules/05-frontend-web-mobile.md` exige justificar divergência dos mockups; esta é a
justificativa. O CSS atual tem ~80 arquivos BEM puro, só 8 tokens de cor e centenas de hex soltos
(`#ffffff` 95×, `#1f3450` 73×), o que impede trocar o tema em um ponto.

## Decisão

1. Visual ERP denso e neutro; **nenhuma mudança de funcionalidade**. Textos, roles, `aria-*` e
   fluxos permanecem; só classes, CSS e estrutura visual mudam.
2. Fundação antes das telas (B0): tokens semânticos em `src/index.css` (neutros, estado,
   espaçamento, raio, sombra, tipografia, densidade) e substituição mecânica dos hex soltos por
   `var(--...)`, valor a valor, de modo que a imagem final fique idêntica.
3. Só depois a troca de paleta e fonte (B0.3), aprovada pelo usuário. Fonte candidata: Inter via
   `@fontsource` (local, compatível com a CSP de `vercel.json`); mono só para códigos e números.
4. Componentes compartilhados em `shared/ui` (Modal, DataTable, Badge, PageHeader, Panel,
   EmptyState), shell com topbar/breadcrumbs, depois telas uma a uma com OK por tela.
5. Sem biblioteca de UI nem Tailwind: não há ganho que justifique nova dependência estrutural.

## Consequências

- tema trocável em um único `:root`;
- cada tela é validada com lint, typecheck, testes, build, e2e quando houver, e capturas
  antes/depois em 1440, 1024 e 390 px;
- os modais sem Escape/focus trap e as tabelas sem semântica (A11, A13) são resolvidos pelos
  componentes compartilhados, não remendados antes;
- durante a migração coexistem telas no visual antigo e no novo.
