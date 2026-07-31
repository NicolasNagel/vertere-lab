---
# Regras de auth/segurança/LGPD — carrega ao tocar identidade ou dado pessoal.
paths:
  - "backend/app/modules/identity/**"
  - "backend/app/core/security.py"
  - "backend/app/modules/owners/**"
  - "backend/app/modules/patients/**"
---
# Regras de Autenticação, Autorização, Segurança e LGPD

## Autenticação
- Backend controla credencial e sessão — nunca delegue isso ao frontend.
- Senha com hash forte e salt; recuperação por token de uso único com expiração.
- Proteção contra enumeração de usuário/e-mail; rate limit em login.
- Sessão revogável; access token curto + refresh rotativo, ou sessão opaca equivalente.
- Cookie `HttpOnly` + `Secure` quando usado; usuário inativo **não renova sessão**.
- Mudança crítica de conta pode revogar sessões ativas.

## Autorização
- RBAC com permissão granular (`resource.action`); papel é agrupador, nunca hardcoded no domínio.
- Escopo por clínica sempre presente na checagem; **deny by default**.
- Checagem acontece em todo caso de uso, não só no router de entrada.
- Proteção horizontal (outra clínica) e vertical (papel insuficiente) — teste os dois.
- Alteração de papel é auditada; permissão crítica pode exigir reautenticação (step-up).
- Service account interna usa privilégio mínimo, nunca acesso amplo "para facilitar".

## LGPD
- Minimização e finalidade: campo novo em `Owner`/`Patient` precisa justificar por que é
  necessário para um fluxo real do PRD — decisão de retenção por categoria de dado é jurídica,
  não da engenharia; sem essa decisão, implemente só soft-delete, não eliminação automática.
- Direito de correção e exportação do titular precisam existir antes de produção, mesmo que via
  admin no MVP.
- Anonimização obrigatória para qualquer dado usado em analytics.
- **Dado real nunca entra em CI** nem em ambiente de dev/staging sem anonimização real (não
  "acho que não dá pra identificar" — ver `10-data-migration.md` para dado de teste da migração).
- Suporte/atendimento interno vê só o necessário para a tarefa, não o cadastro inteiro por padrão.
- Log mascarado; existe política de resposta a incidente (mesmo que simples, precisa existir por
  escrito antes de produção).

## API
- TLS obrigatório; CORS restrito ao(s) domínio(s) conhecido(s); CSRF conforme a estratégia de
  cookie escolhida.
- Limite de tamanho de payload; validação de entrada sempre no backend (Zod no frontend é só UX).
- Headers de segurança configurados no deploy; rate limit nos endpoints sensíveis.
- Proteção SSRF em toda integração que aceita URL externa.
- **Nunca aceite mass assignment** — `extra='forbid'` no schema de entrada.
- Mensagem de erro não vaza detalhe interno (stack, query, nome de tabela).

## Segredos
Só via variável de ambiente/secret manager; nunca commit, nunca log. Ambiente separado por
estágio (dev/staging/produção); rotação de segredo crítico; escopo mínimo por credencial.

## Nunca aparece em log
Senha · token · cookie · documento completo do titular · conteúdo completo de laudo · arquivo
binário · payload bruto com PII · connection string.
