# ADR-011 — Limites de compatibilidade após a remediação estrutural

## Status

Aceito — 2026-08-09.

## Contexto

A remediação consolidou período livre, escopo clínico, acesso atômico, Unit of Work e contratos
frontend. Renomear agregados históricos ou redesenhar `Owner`, preços e coleta na mesma sequência
aumentaria o risco de migration e desviaria do núcleo transacional.

## Decisão

1. `MonthlyClosure` permanece como nome histórico, mas todo contrato novo usa
   `period_start`/`period_end`.
2. `Owner` continua embutido em `Patient`; permissões `owners.*` ficam inativas por ausência de
   casos de uso.
3. `Exam` mantém o preço vigente; snapshots do atendimento são a proteção histórica.
4. códigos históricos de coleta permanecem aceitos até existir taxonomia semântica aprovada.
5. `/users/{id}/role` permanece depreciado; `/users/{id}/access` é o contrato canônico.

Essas decisões são compatibilidade temporária, não o modelo-alvo. O backlog e os critérios de
saída ficam em `docs/08-divida-tecnica.md`.

## Consequências

- reduzimos mudanças destrutivas durante a estabilização do núcleo;
- clientes novos têm contratos inequívocos de período e acesso;
- documentação deve distinguir domínio-alvo de implementação atual;
- os itens não podem ser removidos sem migration expand/contract e janela de compatibilidade.

## Reavaliação

Revisar quando houver requisito comercial de preço versionado, deduplicação de tutor, nova
taxonomia de coleta ou versão maior da API. DT-006 bloqueia release do núcleo até a jornada E2E
real estar automatizada.
