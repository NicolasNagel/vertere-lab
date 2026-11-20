---
description: Fecha uma fatia — /validar, QA independente, revisão independente e commit com rastreabilidade.
argument-hint: "<fatia: número/nome do plano aprovado>"
---
# /fechar-fatia — da fatia pronta ao commit
Executa os passos 3 a 8 do fluxo de fatia do `AGENTS.md`. Use quando o código da fatia está
escrito e o plano aprovado (com **critérios de aceite**) ainda está à mão. Sem critérios de
aceite não há contra o que verificar: volte ao `/planejar-fatia`.

## 1. Pré-condições
- `git branch --show-current` **não** é `main`. Se for, crie a branch da rodada antes de seguir
  (`git switch -c feat/…`); nunca commite na `main`.
- `git status`: separe o que pertence a esta fatia do que não pertence (planilha `.xlsx` da
  raiz, artefatos de QA, mudança de outra fatia). Só entra no commit o que é da fatia.

## 2. Gate (`/validar`)
Rode `/validar` no escopo tocado, mais Playwright se houve mudança de tela. **Conserte até
verde.** Não siga com vermelho.

## 3. QA independente
Chame o subagente `qa-fatia` passando: os **critérios de aceite** (texto literal do plano), a
branch e o intervalo do diff, e o que ficou fora do escopo. Não passe a sua opinião sobre o que
"deve funcionar". Exija a tabela por critério com evidência.

## 4. Revisão independente
Chame `revisor-codigo` com o mesmo plano e critérios; no parecer ele deve dizer, por critério, se
o diff o implementa. Se a fatia tocou dinheiro, permissão, escopo de clínica, atendimento,
fechamento, importação ou identidade, chame também `auditor-integridade`. Rode QA e revisão em
paralelo quando forem independentes.

## 5. Achados
- Bloqueante (QA `reprovado`, revisor `bloqueado`, critério `não atendido`): corrija, rode
  `/validar` de novo e repita só o passo que reprovou.
- Ressalva: registre em `docs/pendencias-redesign-operacao.md` (ou no registro da área) com o
  motivo, ou corrija. Nunca deixe sumir.
- Aceitar um bloqueante sem corrigir só com ordem explícita do usuário, citada no commit.

## 6. Commit
```bash
git add <caminhos explícitos da fatia>     # nunca -A nem .
git commit                                 # mensagem abaixo
```
Mensagem em inglês: `tipo(escopo): resumo` na primeira linha (feat, fix, refactor, test, docs,
chore) e um corpo curto com:
- o que mudou e por quê;
- **critérios de aceite atendidos** (uma linha cada);
- gates executados, veredito do QA e do revisor, achados aceitos ou adiados;
- terminar com a linha de coautoria definida no contexto da sessão.

Depois: `git status` limpo para a fatia e `git log -1 --stat` conferido.

## 7. Reportar
Diga: hash e título do commit, critérios atendidos, vereditos de QA e revisor, pendências
registradas e o que **não** pôde ser executado. Aguarde o sinal explícito para a próxima fatia.
`push`, PR, merge, `amend`, `rebase` e `force` só a pedido do usuário.
