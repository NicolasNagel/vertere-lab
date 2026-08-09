# Frontend do Vertere Lab

Aplicação React 19 + TypeScript responsável pelos fluxos de identidade, cadastros, atendimento e
fechamento financeiro.

## Executar

Na raiz do repositório, instale o workspace Python. Nesta pasta:

```powershell
npm ci
npm run dev
```

O frontend usa `/api/v1` e envia o cookie de sessão com `credentials: include`. Em desenvolvimento,
o proxy de [`vite.config.ts`](vite.config.ts) deve apontar para o backend local. Opcionalmente,
`VITE_API_BASE_URL` define outra base no build.

## Organização

- `src/app`: providers e rotas;
- `src/features`: APIs, hooks, formulários e componentes por domínio;
- `src/shared/api`: cliente HTTP, erros e contratos gerados;
- `src/shared/ui`: componentes reutilizáveis;
- `e2e`: cenários Playwright com axe.

Estado remoto pertence ao TanStack Query. Formulários complexos usam React Hook Form e Zod apenas
para feedback de experiência; o backend permanece a autoridade de validação e autorização.

## Contratos da API

```powershell
npm run api:generate
npm run api:check
```

O primeiro comando exporta o OpenAPI do backend e gera `src/shared/api/generated.ts`. O segundo
falha quando o contrato versionado diverge da regeneração. Mappers de feature convertem os nomes
`snake_case` da API para modelos de apresentação em `camelCase`.

## Qualidade

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

Playwright executa desktop, tablet e mobile. Fluxos críticos verificam acessibilidade com axe.
Para reduzir falsos timeouts em máquinas limitadas, Vitest pode ser executado serialmente:

```powershell
npx vitest run --maxWorkers=1 --fileParallelism=false
```

## Segurança do cliente

- não armazenar token ou cookie em `localStorage`;
- tratar `401` e `403` separadamente;
- limpar cache ao trocar usuário, papel ou memberships;
- incluir escopo clínico nas query keys;
- enviar `Idempotency-Key` ao confirmar atendimento ou fechar período;
- nunca considerar botão oculto como autorização.

Veja o [guia operacional principal](../README.md) e as
[limitações conhecidas](../docs/08-divida-tecnica.md).
