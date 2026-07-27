# ADR-008 — Resolução das pendências de segurança do ADR-007

- **Status**: aceita
- **Data**: 2026-07-27
- **Decisores**: Nicolas Nagel (PO/dev), Claude (execução)

## Contexto

O ADR-007 registrou três achados de uma verificação manual adversarial no módulo de Usuários &
Permissões e deixou dois deles como pendência explícita, sem corrigir: (1) edição de permissões
de perfil sem proteção de autoexclusão — um admin podia remover `roles.manage` do próprio perfil
e travar o sistema sem caminho de volta pela UI/API; (2) a suspeita de que o mesmo padrão de
concorrência leitura-depois-escrita existisse em outros módulos. Uma segunda rodada de teste
adversarial, pedida explicitamente ("force o erro mesmo para encontrar bugs"), encontrou um
terceiro problema não previsto: **o endpoint de login não tinha nenhuma proteção contra força
bruta** — 15 tentativas de senha errada em paralelo, todas `401`, sem throttling, violando
`.claude/rules/auth-security-lgpd.md` ("rate limit em login") explicitamente. Também apareceu,
por inspeção do próprio schema, ausência de `max_length` em campos de texto (`full_name`,
`name`/`description` de perfil), permitindo payload de até 100 mil caracteres.

Pedido explícito do usuário: "Defina as prioridades e as corrija após isso." Prioridade definida
e comunicada antes de codificar: (1) self-lockout na edição de permissões — maior severidade,
outage real sem recuperação; (2) limite de tamanho — trivial, baixo risco; (3) rate limit no
login — maior escopo (tabela nova, caso de uso alterado).

## Decisão

**1. Self-lockout organizacional em `update_role_permissions`.** Extraí `CONTROL_PERMISSIONS`
(antes duplicado como `_CONTROL_PERMISSIONS` em `assign_role.py` e `deactivate_user.py`) para
`app/modules/identity/domain/constants.py` — DRY no limiar de 3 usos (regra do projeto) — e
adicionei `roles.manage` ao conjunto, que faltava mesmo nos dois casos de uso que já tinham
proteção. `UpdateRolePermissionsUseCase` agora bloqueia (`SelfLockoutError`, `409`) qualquer
edição que deixaria zero usuários ativos com uma permissão de controle **em toda a organização**
— não só para o ator, ao contrário de `assign_role`/`deactivate_user` (autoexclusão individual),
porque editar um papel afeta todo mundo que o tem. Isso exigiu estender
`UserRepository.count_active_users_with_permission` com um novo parâmetro `exclude_role_id`
(além do já existente `exclude_user_id`), tanto no protocolo quanto na implementação SQLAlchemy
e no fake de teste.

**2. `max_length` explícito** em `UserCreateRequest.full_name` (200), `RoleCreateRequest.name`
(100)/`description` (1000)/`permissions` (200 itens), `RoleUpdateRequest.permissions` (200
itens), e `LoginRequest.login` (254, teto de e-mail do RFC 5321)/`password` (200 — sem isso, um
payload arbitrariamente grande vira trabalho de hash Argon2 sobre lixo antes de rejeitar).

**3. Rate limit de login persistido no PostgreSQL.** Tabela `login_failures` (`login`,
`occurred_at`, índice composto) — deliberadamente não Redis nem memória de processo: a app roda
como Function stateless (`CLAUDE.md` — "Vercel é stateless"), e Redis só entra com justificativa
medida. `LoginUseCase` ganhou `LoginFailureRepository` + `rate_limit_max_attempts`/
`rate_limit_window`: antes de verificar a senha (não depois — rate limit que só age depois do
hash Argon2 já pagou o custo que deveria evitar), conta falhas recentes por login normalizado
(protege contra força bruta numa conta específica, inclusive contra e-mail inexistente — mesma
lógica de `.claude/rules/auth-security-lgpd.md` sobre enumeração); acima do limite,
`RateLimitedError` → novo `ErrorCode.RATE_LIMITED` → `429`. Falha registra, sucesso limpa o
contador. Configurável via `Settings.login_rate_limit_max_attempts` (padrão 5) e
`login_rate_limit_window_minutes` (padrão 15).

**Bug descoberto implementando o item 3, corrigido no mesmo commit**: o registro de falha (e o
`audit_log` de `auth.login_failed`) nunca sobrevivia de verdade — a exceção de credencial
inválida propagava para fora do `with uow:` do router, e o unit of work faz rollback em qualquer
exceção não tratada, descartando os dois junto. Só apareceu porque o teste de integração real
(Postgres, não fake) provou que a 6ª tentativa ainda passava. Corrigido capturando
`InvalidCredentialsError`/`AccountInactiveError`/`RateLimitedError` dentro do `with uow:` no
router, commitando explicitamente antes de re-lançar. **Consequência não corrigida aqui**: esse
mesmo padrão (side-effect esperado em caminho de exceção descartado pelo rollback do unit of
work) pode existir em qualquer outro endpoint que grave auditoria em um caminho de falha
conhecida — não auditado nesta sessão além do login.

## Alternativas consideradas

- **Redis para o rate limit** — rejeitada: nenhuma justificativa medida além deste caso único,
  que uma tabela simples já resolve sem introduzir peça de infraestrutura nova (regra do
  `CLAUDE.md`: "Redis é opcional, só entra com justificativa medida").
- **Rate limit por IP em vez de (ou além de) por login** — rejeitada por escopo: protege contra
  um ataque diferente (enumeração de e-mails a partir de um IP, não força bruta numa conta
  específica). Registrado como pendência abaixo, não implementado.
- **Aplicar a mesma proteção de self-lockout em `clinics`/`veterinarians`** (mesmo padrão de
  concorrência leitura-depois-escrita, suspeitado no ADR-007) — não investigado nesta sessão;
  seguiria fora de escopo do módulo de identidade. Pendência mantida.
- **Corrigir os dois problemas encontrados em código não relacionado** (`attendances`, ainda não
  commitado por outra sessão) para destravar o gate de `Stop` — feito, mas deliberadamente
  minimalista e mecânico: um import não usado removido, um método `update` faltante no fake de
  teste adicionado espelhando o padrão já usado em todo o resto do arquivo (`self._x[id] = obj`),
  sem tocar em nenhuma lógica de negócio daquele módulo. Commitado separadamente deste ADR — não
  é uma decisão de produto, é destravar um gate compartilhado.

## Consequências — pendências explícitas

1. **Rate limit é só por login, não por IP.** Um ataque distribuído (mesma senha contra muitas
   contas, cada uma de um IP diferente, ou o inverso — muitas senhas contra uma conta usando IPs
   rotativos) não é coberto por essa dimensão sozinha. Decisão consciente de escopo, não lacuna
   descoberta tarde — mas fica registrada para quando for medido como necessário.
2. **O mesmo padrão de concorrência leitura-depois-escrita (suspeitado no ADR-007) segue sem
   auditoria formal em `clinics`/`veterinarians`/outros módulos com `expected_row_version`.**
3. **O padrão "efeito colateral gravado no caminho de exceção, perdido no rollback do unit of
   work" (achado neste ADR) não foi auditado em outros endpoints** — só o login foi corrigido.
   Qualquer outro fluxo que grave `audit_log` ou outro estado a partir de um branch de erro
   esperado (não uma exceção não tratada) pode ter o mesmo problema silencioso.
4. **Numeração de migration**: `0015_create_login_failures.py` foi encadeada em `0012` (última
   migration commitada), não nas `0013`/`0014` que existiam localmente sem commit (trabalho de
   importação de outra sessão). Esse outro trabalho se renumerou para `0016`/`0017` encadeando
   depois da `0015`, resolvendo o conflito de numeração sem intervenção — mas fica documentado
   aqui porque a resolução foi automática/externa a este ADR, não uma escolha registrada em
   conjunto.

## Verificação

Backend completo: ruff, mypy (291 arquivos), pytest — 277 de 278 testes passando (a única falha,
`test_import_exams_partial_success_reports_row_errors`, é do módulo `imports` de outra sessão,
não relacionada). 38 testes em `identity` (unit + integração com Postgres real via Testcontainers)
cobrindo as três correções, incluindo um teste de concorrência real (`asyncio.gather`, não
sequencial) para o self-lockout e um teste ponta a ponta reproduzindo exatamente o cenário de
força bruta (5 tentativas erradas + `429` na 6ª, mesmo com a senha certa).

**Verificação manual em 2026-07-27**, ambiente descartável (Postgres em container, backend e
frontend locais), logado como `SUPER_ADMIN` de teste: as 15 tentativas de senha errada em
paralelo agora resultam em `401` seguido de `429` consistente; remover `roles.manage` do próprio
perfil do único admin agora retorna `409` com mensagem clara; payload de 100 mil caracteres em
`full_name`/perfil agora retorna `422`. Testes adicionais além dos já feitos no ADR-007: usuário
com só `users.update` (sem `roles.assign`) tentando promover a si mesmo a `SUPER_ADMIN` — `403`;
cookie de sessão forjado — `401`; UUID malformado em path e `scope` de perfil inválido — `422`
limpo, sem `500`; senha vazia no login — `422`. A correção de concorrência do ADR-007 (CAS em
`replace_permissions`) foi re-testada e continua íntegra (`[200, 409]`). Ambiente de QA
descartado ao final.
