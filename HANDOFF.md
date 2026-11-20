# Handoff — 2026-11-20 · rodada de pendências do redesign (fatias 1–7)

Fonte da verdade do que ainda está aberto: `docs/pendencias-redesign-operacao.md`. Este arquivo
só diz onde o trabalho parou e o que não é óbvio. Os addenda antigos (julho a setembro) foram
removidos; o histórico está no git.

## Feito nesta sessão
- Rodada de pendências do redesign, uma fatia por branch, todas com QA e revisão independentes,
  exceto a fatia 7 (ver abaixo): tetos numéricos (quantidade 1–999, preço/taxa até R$ 99.999,99,
  máx. 100 itens por atendimento) com 422 em vez de 500; erros por linha nas importações
  (NUL/NaN/Infinity/estouro); busca sem acento e simétrica calculada no PostgreSQL
  (`unaccent`, migration 0044); auditoria de paciente com quem/o quê/quando (só campos alterados;
  telefone e documento viram `[alterado]`); bloco de detalhe compartilhado (`detail-block.tsx`).
  Commits `8690fed`, `b096fef`.
- Fatia 6, isolamento por clínica (`228c41d`, mesclada em `main` por `c6751da`): usuário de clínica
  não lista, ativa, desativa nem altera papel/acesso de usuário de outra clínica ou do laboratório;
  não vincula veterinário invisível; só concede papel de clínica com permissões contidas nas suas;
  perfis de acesso só pelo laboratório. Regra central em
  `backend/app/modules/identity/application/user_scope.py`. Teste: `test_clinic_scope_isolation_api.py`.
  Também: barra lateral fechada no mobile fora da ordem de Tab; `aria-*` inválido removido de `tr`.
- Fatia "menu por permissão" (`ad0673b`, branch `feat/sidebar-permission-filter`, **ainda não
  mesclada**): menu lateral só mostra Clínicas/Veterinários/Exames/Pacientes com a permissão
  `*.read` correspondente; 403 nas listas de Clínicas e Veterinários mostra mensagem de permissão.
  Pulou QA/revisor independentes de propósito (só visibilidade de UI, sem dinheiro/tenant/identidade;
  dito no corpo do commit).
- Fatia 7: este arquivo reescrito (branch `docs/handoff-real-state`).

## Estado do gate
- backend: verde (ruff, mypy, pytest 365, após a política de veterinários). 
- frontend: verde em `ad0673b` (tsc, oxlint, vitest 157, playwright 192, build verificado na fatia 6).
- migrações: head em `0044_enable_unaccent_extension` (downgrade é no-op de propósito: não remove a extensão).
- Não rodado: nenhum QA real (`qa-fatia`) sobre a fatia do menu.

## Em andamento (não finalizado)
- Nada pela metade no código. Tudo está na `main` local e no PR #2 (head `feat/redesign-pendencias-round`, ainda sem mesclar no remoto). 

## Armadilhas conhecidas
- Docker precisa ser ligado à mão; sem ele todos os testes de integração dão erro de setup, não falha.
- Duas suítes pytest/testcontainers ao mesmo tempo causam erro de setup: rode em série.
- Git Bash: use `MSYS_NO_PATHCONV=1`; o shell mutila `\x00` e `\\1` em heredoc, então escreva scripts
  com a ferramenta de arquivo. O projeto não usa prettier: não rode, ele reformata arquivos alheios.
- Fora de escopo = 404, nunca 403 (não confirma existência). Papéis semeados CLINIC_ADMIN,
  VETERINARIAN e CLINIC_STAFF têm zero permissões; o LAB_ADMIN semeado não tem `roles.manage`.
- QA local: Postgres `vertere-qa-pg` (porta 55432, volume `vertere-qa-pg-data`), uvicorn 8321,
  Vite 5173, login `admin@qa.local`. Só dado sintético, com muitos usuários `qa7-`/`qa8-`.
  Os diretórios de QA com senhas sintéticas já foram apagados; servidores e container continuam ligados.
- A planilha `.xlsx` da raiz é untracked de propósito; não commitar.

## Próximo passo recomendado
1. Confirmar com o produto a política de veterinários já mesclada: ator de clínica só altera ou
   desativa veterinário cujos vínculos são todos com clínicas dele (ajuste pequeno se mudar).
2. Rodar no banco REAL, antes do deploy, a consulta abaixo; qualquer `over_limit > 0` é dado
   que o teto novo (qtd 999, preço R$ 99.999,99) deixaria inválido. No banco de QA sintético
   o resultado foi zero em todas as linhas (os máximos de 99999.99 e 999 vêm de testes de QA).
3. Revisar e mesclar o PR #2 (branch `feat/redesign-pendencias-round`, base `main`); a consulta de limites
   já deu zero linhas acima do teto nos bancos de QA e de desenvolvimento (este está na migration 0039).

```sql
select 'exams.price_base' c, max(price_base) m, count(*) filter (where price_base > 99999.99) over_limit from exams
union all select 'attendance_exams.price_base', max(price_base), count(*) filter (where price_base > 99999.99) from attendance_exams
union all select 'attendance_exams.discount_amount (limit 99999.99*999)', max(discount_amount), count(*) filter (where discount_amount > 99999.99*999) from attendance_exams
union all select 'clinic_fee_rules.fee_amount', max(fee_amount), count(*) filter (where fee_amount > 99999.99) from clinic_fee_rules
union all select 'on_call_fee_settings.fee_amount', max(fee_amount), count(*) filter (where fee_amount > 99999.99) from on_call_fee_settings
union all select 'urgency_fee_settings.fee_amount', max(fee_amount), count(*) filter (where fee_amount > 99999.99) from urgency_fee_settings
union all select 'attendance_exams.quantity (limit 999)', max(quantity), count(*) filter (where quantity > 999) from attendance_exams;
```

## Pendências fora do código
- Abertas e priorizadas em `docs/pendencias-redesign-operacao.md`: acessibilidade restante
  (`document.title` por rota, skip-link, regiões vivas, Esc cancela bloco, foco do menu Ações),
  Novo Protocolo mostrando pacientes de outras clínicas, TOCTOU em ativar/desativar/papel,
  409 de e-mail em `create_user` enumerando e-mails, `audit_log` sem leitura pela API,
  `row_version` transversal, QA de Exames/Usuários/Fechamento, coluna "Valor" sem `pricing.read`.
- Deploy (conta/infra, não código): projetos Vercel de frontend e backend, PostgreSQL gerenciado,
  `TRUSTED_BROWSER_ORIGINS` com o domínio real (sem isso login e mutações dão
  `403 CSRF_ORIGIN_FORBIDDEN`) e job controlado para `alembic upgrade head`.
