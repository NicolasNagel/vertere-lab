# ADR-007 — Tela de Usuários & Permissões e correção de concorrência em perfis

- **Status**: aceita
- **Data**: 2026-07-27
- **Decisores**: Nicolas Nagel (PO/dev), Claude (execução)

## Contexto

O backend de `backend/app/modules/identity/` (usuários, papéis, permissões, RBAC) já existia,
testado, mas sem nenhuma tela de administração — só acessível via API direta. Isso bloqueava a
prioridade #1 do projeto (`CLAUDE.md` §"Prioridade de implementação": "autenticação, usuários,
papéis e permissões" antes de qualquer outro módulo).

O mockup (`assets/features/screens/9-usuarios-permissoes.html`) e o `spec-pages.md`
(linha 597-660) descrevem um fluxo de **convite por e-mail** (`POST /users/invite`, "convite
pendente", "reenviar convite") e nomes de permissão fictícios (`USER_MANAGE`/`PERMISSION_MANAGE`)
que **não existem no backend real** — ele cria o usuário imediatamente com uma
`temporary_password` retornada de forma síncrona, e usa códigos `resource.action`
(`users.read`, `roles.assign`, etc.). Essa divergência foi decidida explicitamente com o usuário
antes de codificar (via `AskUserQuestion`, não assumida), junto de mais duas decisões de escopo:
só os 6 papéis internos do laboratório aparecem na tela (os 3 papéis `CLINIC` não têm
`ClinicMembership` real ainda — Fase 2); e CRUD completo de perfis de permissão entra nesta
entrega, já que o backend já suportava criar/editar perfis.

Depois da implementação (5 fatias: backend de reativação de usuário, camada de API do frontend,
tela de usuários, tela de perfis de permissão, rotas/navegação) e do gate automatizado
(`ruff`+`mypy`+`pytest` no backend, `oxlint`+`tsc`+`vitest` no frontend, todos verdes), o usuário
pediu explicitamente uma verificação adversarial: rodar o sistema de verdade no Chrome, forçando
erros e permissões erradas, porque "esse é o módulo mais importante do sistema". Essa verificação
achou 3 bugs reais que o gate automatizado não pegava — este ADR existe para registrar o que foi
corrigido e, principalmente, o que **não** foi, para não virar suposição silenciosa depois.

## Decisão

**1. Fluxo real (sem convite por e-mail) confirmado em produção.** A tela cria o usuário e mostra
a `temporary_password` uma única vez num diálogo modal — única exceção ao padrão mestre-detalhe
sem overlay do resto do app, porque a senha não pode ser mostrada de novo e precisa de
reconhecimento explícito.

**2. `PATCH /users/{id}/activate` adicionado** (endpoint novo, simétrico a `deactivate`), com
permissão `users.activate` própria (não reaproveita `users.deactivate` para as duas direções, para
manter a auditoria honesta sobre qual ação foi de fato tomada).

**3. Política de retry do TanStack Query corrigida globalmente**
(`frontend/src/app/providers.tsx`, `shouldRetry`): erro 4xx nunca é retentado, só 5xx/falha de
rede. **Achado em teste manual**: sem isso, uma tela sem a permissão necessária navegada
diretamente pela URL ficava presa em `status: 'pending'` para sempre (o retry entrava em
`fetchStatus: 'paused'` e nunca resolvia para `error`), e a UI caía no estado vazio genérico
("Nenhum usuário encontrado") em vez de "Você não tem permissão" — uma tela sem dado nenhum e sem
explicação do porquê. Correção é de escopo global (afeta toda query do app), não só deste módulo.

**4. Erro de domínio de `deactivate`/`activate` agora é exibido na UI** (`UserDetail`). Antes,
uma rejeição do backend (por exemplo o bloqueio de autoexclusão) não aparecia em lugar nenhum — o
admin clicava "Desativar", nada acontecia visivelmente, e não havia como saber se tinha funcionado,
falhado, ou se o app estava quebrado. `describeError` (antes duplicada 3x) foi extraída para
`shared/api/describe-error.ts`.

**5. Edição de permissões de perfil agora usa compare-and-swap atômico no banco**, não
leitura-depois-escrita. **Achado em teste manual, o mais sério dos três**: duas requisições
`PATCH /permission-profiles/{id}` disparadas de verdade em paralelo (`Promise.all` no navegador,
confirmado depois com `asyncio.gather` direto no ASGI) usando o mesmo `expected_row_version`
**as duas retornavam 200**, e uma edição sumia silenciosamente por cima da outra — o
`UpdateRolePermissionsUseCase` fazia `get_by_id` (sem lock) → comparar versão → escrever, uma
janela clássica de TOCTOU sob concorrência real. Corrigido com um único
`UPDATE ... WHERE id = :id AND row_version = :expected` (retorna `rowcount` zero em caso de
conflito, sem SELECT prévio) em `SqlAlchemyRoleRepository.replace_permissions`, que agora recebe
`expected_row_version` e devolve `bool`. Teste de regressão usa concorrência real
(`asyncio.gather`, duas requisições HTTP de verdade, não sequencial fingindo concorrência —
exigência de `.claude/rules/testing.md`), e assert que os status finais são `[200, 409]`.

## Alternativas consideradas

- **`SELECT ... FOR UPDATE` (lock pessimista) antes do compare** — rejeitada em favor do UPDATE
  condicional: uma única instrução atômica é mais simples, não precisa manter uma transação
  aberta segurando lock entre o SELECT e o UPDATE, e o resultado (`rowcount == 0`) já diz
  diretamente se houve conflito, sem precisar de uma segunda leitura pós-lock.
- **Aplicar o mesmo fix de concorrência em `clinics`/`veterinarians` nesta entrega**, já que o
  mesmo padrão leitura-depois-escrita existe lá (`update_clinic.py` e equivalentes) — rejeitada
  por escopo: esta fatia é sobre o módulo de identidade; estender o fix a outros módulos sem pedido
  explícito seria escopo novo não decidido. Fica registrado como pendência abaixo.
- **Proteger self-lockout na edição de permissões de perfil** (mesma proteção que já existe em
  `deactivate_user`/`assign_role`) — considerada durante a verificação manual, mas **não
  implementada nesta entrega**: expandiria escopo sem decisão do usuário, e o teste que provaria o
  bug ao vivo (remover `roles.manage` do próprio perfil do único admin) arriscava travar o
  ambiente de QA sem caminho de volta pela UI. Documentada como pendência de maior severidade
  abaixo, não corrigida.

## Consequências — pendências explícitas

1. **Edição de permissões de perfil não tem proteção de autoexclusão.**
   `UpdateRolePermissionsUseCase` só valida `row_version`, não verifica se a mudança removeria a
   última pessoa capaz de gerenciar usuários/permissões — ao contrário de `deactivate_user.py` e
   `assign_role.py`, que já têm essa checagem (`_CONTROL_PERMISSIONS`). Um admin pode remover
   `roles.manage`/`users.deactivate`/`users.update` do **próprio** perfil sem aviso e ficar
   travado sem caminho de volta pela UI/API — só recuperável com acesso direto ao banco. É o
   achado de maior severidade desta verificação. **Ação pendente**: decidir se a mesma checagem de
   `_CONTROL_PERMISSIONS` deve se estender a `UpdateRolePermissionsUseCase` (aplicada ao perfil do
   próprio ator, verificando se ele ficaria sem `roles.manage`/`users.deactivate`/`users.update`
   após a mudança) antes de considerar este módulo pronto para produção.
2. **O mesmo padrão de concorrência leitura-depois-escrita (corrigido aqui só em `roles`)
   provavelmente existe em outros módulos** — confirmado por inspeção em
   `clinics/application/update_clinic.py` (`if clinic.row_version != command.expected_row_version:
   raise ConflictError`, sem lock nem UPDATE condicional). Não verificado em `veterinarians`,
   `patients`, `catalog` nesta sessão, mas o mesmo formato de código (`get_by_id` → comparar →
   `save`) é o padrão estabelecido no projeto para "edição com row_version", então é provável que
   se repita em todos. **Ação pendente**: auditoria dedicada de todo `update_*` com
   `expected_row_version` no projeto, convertendo para UPDATE condicional onde a corrida for
   real (edição concorrente por dois atores diferentes, não só o mesmo ator recarregando a página).
3. **Papéis de escopo `CLINIC` (`CLINIC_ADMIN`, `VETERINARIAN`, `CLINIC_STAFF`) continuam sem
   `ClinicMembership` real e sem nenhuma permissão seedada** — decisão original de excluí-los da
   tela se mantém correta, mas o modelo de domínio (`docs/03-modelo-de-dominio.md`) já lista
   `ClinicMembership` como entidade esperada. Constrói-la é pré-requisito para esses 3 papéis
   deixarem de ser placeholder.
4. **Sem fluxo de convite por e-mail** — decisão consciente desta entrega (contexto acima), não
   um bug, mas registrado para não ser "descoberto" de novo numa fatia futura sem ADR: se o
   produto vier a exigir onboarding assíncrono por e-mail (em vez de o admin comunicar a senha
   temporária manualmente), é uma feature nova — token pendente, expiração, outbox de e-mail fora
   da transação crítica (regra de `CLAUDE.md`) — não uma correção deste módulo.
5. **Sem exibição de "última atividade"/último login do usuário** — o mockup mostra essa coluna;
   `UserListItemRead` só tem `created_at`. Omitido conscientemente (Fatia 3), não implementado
   porque exigiria rastrear `last_seen_at` agregado por usuário (haveria dado parecido em
   `Session.last_seen_at`, mas não há endpoint que agregue isso por usuário hoje).
6. **Teste de concorrência real cobre só `roles.update_permissions`.** Os outros fluxos de
   `identity` com `expected_row_version` (nenhum outro além de roles, no momento) ou lock
   (protocolo de atendimento, fechamento — ainda não implementados) precisarão do mesmo padrão de
   teste (`asyncio.gather`, não sequencial) quando existirem.

## Consequências — o que já foi corrigido, não é pendência

- Estado "sem permissão" preso em loading infinito → correção global de retry (`providers.tsx`).
- `RolesPage` sem nenhum tratamento de 403 → branch adicionada, mesma UX de `UsersPage`.
- Ativar/desativar usuário falhando silenciosamente na UI → erro de domínio agora exibido em
  `UserDetail`.
- Corrida de leitura-depois-escrita em `roles.update_permissions` → UPDATE condicional atômico.
- Cobertura de teste que não existia antes desta verificação, adicionada: `activate_user`
  (unit + integração), `update_role_permissions` (unit — nenhum teste existia, nem forbidden, nem
  not-found, nem conflito), revogação de sessão ao desativar usuário (só havia unit test de
  domínio, não integração ponta a ponta), corrida real de dois `PATCH` concorrentes.

## Verificação

Gate automatizado verde: backend (Ruff, mypy estrito, pytest — 223 testes incluindo integração
com PostgreSQL real via Testcontainers); frontend (`tsc -b`, oxlint, vitest — 84 testes).

**Verificação manual em 2026-07-26/27**, Postgres local (`docker run postgres:17-alpine`),
backend e frontend rodando localmente, testado no Chrome como usuário `SUPER_ADMIN` de teste e
como usuário `RECEPTION` criado pela própria tela: criação de usuário com senha temporária,
rejeição de e-mail inválido e de perfil ausente (validação client-side), conflito de e-mail
duplicado (`409`), menu lateral escondendo "Usuários"/"Perfis de permissão" sem
`users.read`/`roles.read`, navegação direta por URL para as duas telas sem permissão (bloqueada
corretamente após o fix do item 3), chamadas diretas à API tentando escalar privilégio (criar
SUPER_ADMIN, apagar permissões do próprio perfil do laboratório) — todas `403`, bloqueio de
autoexclusão (desativar/rebaixar o único admin) confirmado via API e via UI (com o fix do item 4,
mensagem agora visível), payload de XSS (`<img onerror=...>`) no nome do usuário renderizado como
texto puro (React escapa por padrão, sem `dangerouslySetInnerHTML` em nenhum componente),
revogação de sessão ao desativar um usuário ativo (teste de integração novo), e a corrida de dois
`PATCH` concorrentes em `permission-profiles` (reproduzida, corrigida, confirmada corrigida com o
backend reiniciado). Ambiente de QA (container Postgres, servidores dev, usuários de teste)
descartado ao final; nada foi commitado durante a verificação.
