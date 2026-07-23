# ADR-001 — Autenticação: sessão opaca revogável em PostgreSQL + Argon2id

- **Status**: aceita
- **Data**: 2026-07-22
- **Decisores**: Nicolas Nagel (PO/dev), Claude (execução)

## Contexto

A Fase 1 do roadmap (`docs/05-roadmap-backlog.md` §3) exige autenticação, usuários, papéis e
permissões antes de qualquer cadastro estruturante. O gate da fase inclui: usuário ativo entra,
usuário inativo não entra, alteração de papel é auditada. `.claude/rules/auth-security-lgpd.md`
exige sessão revogável ("mudança crítica de conta pode revogar sessões ativas") e
`.claude/rules/globals.md`/`CLAUDE.md` proíbem Redis como fonte de verdade — o backend roda como
função HTTP curta e stateless (hoje local/Docker, com Vercel como destino de deploy previsto), sem
memória persistente entre requisições. Isso descarta qualquer estratégia de revogação que dependa
de estado em processo (blacklist em memória) ou de um cache externo tratado como autoridade.

Se nada fosse decidido, o time acabaria implementando JWT por ser o caminho "óbvio" em FastAPI,
sem confrontar que JWT stateless não revoga sem uma lista de negação — e qualquer lista de negação
precisaria viver em algum lugar central, reabrindo a discussão sobre Redis.

## Decisão

Sessão **opaca e revogável, com PostgreSQL como única fonte de verdade**:

- Login gera um token aleatório de alta entropia (`secrets.token_urlsafe`, 256 bits) — o token em
  si só existe no cookie do cliente, nunca é persistido em texto puro.
- O servidor guarda um **hash SHA-256** do token na tabela `sessions` (`token_hash`), não o token.
  SHA-256 é intencional aqui — o token já tem entropia alta (ao contrário de senha escolhida por
  humano), então um hash rápido e determinístico é o correto: permite `lookup` indexado por
  igualdade; um hash lento (Argon2/bcrypt) só adicionaria latência a cada request sem nenhum ganho
  de segurança real (não há nada para um atacante forçar offline).
- Cookie `HttpOnly` + `Secure` (configurável via `SESSION_COOKIE_SECURE` para permitir dev em
  `http://localhost`) + `SameSite=Lax`.
- TTL curto (`SESSION_TTL_MINUTES`, padrão 30 min) com renovação deslizante a cada request válido
  (implementada em `ResolveSessionUseCase`); TTL estendido quando `remember_me=true`
  (`SESSION_TTL_REMEMBER_ME_DAYS`, padrão 30 dias).
- Revogação é um `UPDATE sessions SET revoked_at = now()` — usado em logout explícito e,
  criticamente, em qualquer mudança crítica de conta (troca de papel, desativação): todas as
  sessões ativas do usuário afetado são revogadas na mesma transação da mudança.
- Múltiplas sessões simultâneas por usuário são permitidas nesta fatia (sem limite de 1 sessão
  ativa) — não há requisito de produto para "single session" ainda; se aparecer, é uma decisão de
  negócio nova, não algo a assumir aqui.
- Hash de senha: **Argon2id via `argon2-cffi`**, não bcrypt/passlib. Argon2id é a recomendação
  atual da OWASP Password Storage Cheat Sheet (memory-hard, resistente a GPU/ASIC); `argon2-cffi`
  é a lib de referência da comunidade Argon2 e está ativamente mantida, ao contrário do `passlib`.

## Alternativas consideradas

- **JWT stateless assinado** — rejeitado: revogar um token antes do seu `exp` natural exigiria uma
  blacklist central (Redis, proibido como fonte de verdade) ou aceitar que "mudança crítica revoga
  sessão" simplesmente não funcione até o token expirar sozinho, o que viola a regra do projeto.
- **JWT de acesso curto + refresh token rotativo em Postgres** — meio-termo descartado: ainda deixa
  uma janela em que o access token continua válido mesmo após revogação (até expirar), e adiciona
  complexidade de rotação sem ganho de performance real, já que o backend já paga uma consulta ao
  Postgres por request de qualquer forma (não há motivo de latência para evitar isso aqui).
- **bcrypt para senha** — alternativa aceitável e ainda robusta, mas Argon2id é a recomendação sem
  ressalvas para software novo hoje, e a lib escolhida está mais ativamente mantida.

## Consequências

- Todo request autenticado paga uma consulta indexada a `sessions` — aceitável (medido nos testes
  de integração, sem indício de gargalo neste volume).
- Nenhuma dependência de Redis ou de qualquer cache externo nesta fatia.
- Revogação é imediata e auditável (fica registrada em `audit_log` via os casos de uso que a
  disparam), diferente de JWT onde "revogado" seria só um estado lógico até expirar.
- Cookie `Secure` exige HTTPS em produção; em dev local, `SESSION_COOKIE_SECURE=false` é necessário
  porque o navegador não envia cookies `Secure` para `http://localhost` fora do Chrome/Edge (que
  tratam `localhost` como contexto seguro) — documentado em `.env.example` (pendente, ver
  `HANDOFF.md`).
- Rollback: nenhuma migration desta decisão é irreversível por si só (tabela nova, sem dado
  legado) — reverter a decisão de arquitetura exigiria nova ADR e uma migração de dados de sessão
  ativa para o novo formato (fora de escopo enquanto não houver motivo concreto para trocar).
- Reforça a regra "PostgreSQL é a única fonte de verdade" de ponta a ponta na fatia de identidade.
