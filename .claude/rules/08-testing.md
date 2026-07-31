---
# Regras de testes — carrega ao tocar a suíte de testes (backend ou frontend).
paths:
  - "backend/tests/**"
  - "frontend/**/*.test.ts"
  - "frontend/**/*.test.tsx"
  - "frontend/tests/**"
---
# Regras de Testes

## Obrigatório
- Teste acompanha a mudança na mesma tarefa; bug corrigido ganha teste de regressão.
- Domínio crítico (atendimento, fechamento) **não depende só de E2E** — precisa de unitário e
  integração também.
- Integração crítica usa **PostgreSQL real** (Testcontainers ou instância isolada) — SQLite não
  valida constraint/lock/concorrência real do Postgres.
- Mock só em fronteira externa (e-mail, storage, integração de terceiro) — nunca no repositório
  que está sendo testado.
- Teste determinístico: relógio controlado, dado sintético, sem dependência de ordem entre testes.

## Backend
- pytest; unitário para regra de domínio isolada; integração para SQLAlchemy/Alembic real.
- API testada via HTTPX/ASGITransport, não só a função do caso de uso isolada.
- Concorrência real testada de verdade (threads/tasks concorrentes, não sequencial fingindo
  concorrência).
- Property-based (Hypothesis) para invariante financeira quando fizer sentido (ex.:
  `grand_total = subtotal - discount_total + surcharge_total` para qualquer combinação válida).
- `coverage.py` para acompanhar branch crítico, não como meta vaidosa.

## Frontend
- Vitest + Testing Library para unidade/componente; MSW para simular contrato de API no teste
  de UI; Playwright para E2E dos fluxos críticos.
- Não teste detalhe de implementação (estrutura interna do componente) — teste comportamento.
- Cubra estado de `loading`, vazio, erro, `403` (sem permissão) e conflito de versão — não só o
  caminho feliz.

## Gates especiais (mudança em atendimento)
Toda mudança em `AttendanceRecord`/`AttendanceExam` testa: permissão · escopo (tenant) ·
idempotência · concorrência real · snapshot (preço/nome não mudam retroativamente) · auditoria ·
impacto no fechamento.

## Gates especiais (mudança em fechamento)
Toda mudança em `MonthlyClosure` testa: elegibilidade de item · soma exata · lock ·
idempotência · imutabilidade pós-fechamento · ajuste · reabertura · auditoria.

## Cenário E2E mínimo do núcleo (docs/06-estrategia-qa.md §3)
1. admin cria usuário e atribui permissão;
2. recepção cria clínica/veterinário/proprietário/paciente;
3. recepção registra e confirma atendimento;
4. financeiro abre prévia e fecha competência;
5. recepção tenta alterar valor de item fechado e recebe bloqueio;
6. financeiro registra ajuste autorizado;
7. usuário de outra clínica tenta acessar e recebe negação.

## Proibições
Mockar o repositório em todos os níveis e chamar isso de "teste de integração" · usar SQLite
para validar comportamento que depende do PostgreSQL · repetir teste flaky esperando que passe
em vez de investigar · reduzir cobertura sem justificativa escrita · usar dado real de produção
em teste.