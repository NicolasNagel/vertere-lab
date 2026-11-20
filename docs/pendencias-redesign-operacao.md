# Pendências — redesign de Operação e pacotes de exames

Lista viva, anotada durante as fatias; corrigir tudo em um laço ao final.
Formato: `[ ]` aberto · `[x]` resolvido.

## Catálogo / pacotes
- [ ] Pacote não tem quantidade por componente: TRANSFUSÃO 1/2 do papel pedem hemograma
      doador + receptor e 3 hematócritos seriados; no catálogo de teste entram 1× cada.
- [x] (era engano) `GET /exams` aceita `page_size` até 100; a grade carrega todas as páginas.
- [x] Rollback da migration 0039 testado com dados (pacote, item de atendimento com snapshot):
      `test_exam_panels_migration_0039_rolls_back_and_reapplies_with_data` — desce para 0038,
      preserva exames/atendimentos, sobe de volta com snapshot `[]`.
- [ ] Script de seed do catálogo de teste mora só no scratchpad; decidir se vira
      `backend/scripts/seed_dev_catalog.py` (preços são fictícios).
- [ ] Telas de Exames & Preços ainda no visual antigo (não ERP); o formulário de pacote herda isso.
- [ ] QA de tablet/celular do formulário de pacote não foi feito.

## Protocolo (a fazer nas próximas fatias)
- [ ] REVERTER: o aviso "Incluso em…" / "Já incluso em…" (fatia 5, `ExamCartGrid` e seu teste) foi
      dispensado em 14/11; remover ao refazer a tela. Repetir exame dentro de pacote é livre.
- [ ] Hora da coleta: decidido NÃO implementar.
- [ ] Campo "Histórico/Observações" do papel: decidido não exibir (`notes` segue no backend).

- [x] Painel "Valor", "Atendimento" e grade de exames refeitos (fatia 5).
- [ ] Grade lista o catálogo inteiro antes de clínica/paciente (só desabilitada); decidir se esconde.
- [ ] Quantidade/desconto por item ficam na lista "Exames selecionados", no fim da página,
      longe da grade; avaliar subir para perto do resumo.
- [ ] Ordem das categorias é Perfis + alfabética; o papel usa Hematologia, Bioquímica,
      Hemogasometria, Urinálise, Coproparasitológicos (catálogo não tem campo de ordem).
- [ ] Pacote por checkbox ignora que o mesmo exame pode ser pedido em quantidade >1 só na lista inferior.
- [x] Axe + overflow na tela de novo protocolo (dropdowns abertos, busca de paciente, grade e resumo)
      em desktop/tablet/mobile: `e2e/attendance-draft.spec.ts` (19/11). Regra `region` desligada só
      nos scans com menu em portal aberto.
- [x] Seta do dropdown "quebrada" na captura imediata: era a transição; com espera de 600 ms fica
      correta (para cima aberto, para baixo fechado). Conferido em captura (19/11).

## Decisões do redesign (14/11) — a implementar, nesta ordem: botões, popover, Novo Protocolo
- [x] Botões (14/11): variantes primary, secondary, cancel (vermelho no hover), danger, ghost + tamanho
  `sm`, altura única de 36 px (`shared/ui/button.*`). Todos os "Cancelar" (17 telas) usam `cancel`,
  "Voltar" de modal usa `secondary`, "Confirmar cancelamento" usa `danger`. Teste
  `button.test.tsx` barra `<button>` cru com rótulo de ação fora de `shared/ui`. Conferido em
  captura (Playwright headless): cancelar neutro → vermelho no hover, danger cheio, altura 36 px.
  Não migrado: botões `ghost` de outras ações (ex.: exportar no fechamento) e botões estilizados
  à mão sem rótulo de ação (tabs, toggles, ícones); revisar quando cada tela for refeita.
- [x] Popover ao clicar na linha da Operação (14/11): resumo (solicitante, paciente e tutor, exames com
  composição do pacote, totais, histórico) e botão Cancelar atendimento (só com `attendances.cancel`
  e status DRAFT/CONFIRMED, reaproveita o modal de motivo). Valores só com `pricing.read`.
  Refeito em 14/11 no padrão do popover de Clínicas (Modal `attendance-popover`, cabeçalho cinza,
  "Abrir atendimento" + menu ⋮ com "Cancelar atendimento" + ×); `anchored-popover` removido.
  4 testes adaptados; conferido em captura (desktop e celular), foco volta à linha, sem erro de console.
  Pendências do popover:
  - [ ] Histórico sem nome do autor: a timeline só devolve `actor_user_id`; precisa de nome no backend.
  - [ ] A coluna "Valor" da tabela continua visível sem `pricing.read` (só o popover respeita);
        decidir se a tabela e os cartões de resumo seguem a mesma regra.
  - [ ] Axe/QA exploratório completo (a11y, segurança) não rodados nesta fatia.
- Novo Protocolo: blocos com padrão único, grade de exames por categoria (opção B), barra de
  resumo fixa, dropdowns próprios (clínica, veterinário, espécie, raça, sexo, unidade de idade).
- Paciente passa a ter idade (número + anos/meses), sexo e raça: importante para laudos.
  Conferir no backend o que já existe; decidir entre guardar número+unidade ou data de nascimento
  aproximada. Exige migration e backfill.
- Tipo de atendimento: Normal, Plantão normal, Plantão especial (`ServiceLevel`); taxa fixa por
  atendimento vinda de Exames & Preços › Taxas de plantão.
- Desconto por exame, em valor livre (R$), limitado ao valor da linha. Conferir como o backend
  guarda desconto hoje; só quem tem `pricing.read` vê e aplica.

## Futuro: regras de cobrança por clínica
Exemplo real: Bicho Urbano paga +R$ 5 nos Check-ups 1, 2 e 3 para cães. O padrão se repete, então
vale um cadastro de regras em vez de ajuste manual, para o sistema calcular e levar o resultado ao
fechamento, painéis e relatórios. Esboço (não implementar antes do núcleo estável):
- `ClinicBillingRule`: clínica, nome, alvo (exame, pacote, categoria ou tudo), espécie opcional,
  efeito (acréscimo fixo, acréscimo %, desconto, preço fixo), vigência, ativa.
- Aplicada na confirmação do atendimento e gravada como snapshot no item (regra, rótulo, valor),
  como já é a composição de pacote. Fechamento e relatórios leem o snapshot, nunca a regra atual.
- Decidido (14/11): a regra é avaliada pelo exame, mas cobra UMA vez por atendimento. Basta o
  atendimento ter ao menos um exame do alvo (ex.: Check-up 1, 2 ou 3) e a espécie certa para somar
  o acréscimo (R$ 5) ao total; vários exames do alvo ou quantidade > 1 não multiplicam.
- Decidido (14/11), demais respostas do financeiro:
  - soma com a taxa de plantão (são linhas independentes no total);
  - vale para o pacote inteiro, no nível do atendimento: o pacote conta como um exame e seus
    componentes não disparam a regra separadamente (confirmar este entendimento ao desenhar);
  - acréscimos de regras diferentes se acumulam; o desconto manual por exame não tem impacto
    sobre eles (o valor da regra é fixo, independe do desconto);
  - reajuste de regra vale só a partir da vigência; atendimento confirmado não muda.
- Total do atendimento (fórmula a testar na reconciliação do fechamento):
  itens − descontos manuais + taxa de plantão + soma das regras da clínica aplicadas.
- Exige ADR, matriz de permissão (`pricing.manage`), auditoria e teste de reconciliação do fechamento.

## Correção de atendimento (editar tudo, sempre) — feito em 14/11
- [x] Backend: PATCH corrige cabeçalho de atendimento confirmado/cancelado (motivo obrigatório, diff
  na auditoria, taxa de plantão e competência recalculadas); `PUT /attendances/{id}/items` inclui,
  remove (fica `CANCELLED` no histórico) e altera quantidade/desconto. Desconto exige
  `attendances.override_price`; sem permissão nova para o resto.
- [x] Atendimento já fechado é editável: a diferença vira `FinancialAdjustment` no próprio
  fechamento (DEBIT aumenta, CREDIT reduz); mudar clínica/data para fora do período reverte tudo no
  fechamento antigo e lança no que cobrir o destino.
- [x] Frontend: "Editar" em cada bloco da tela de detalhe (Solicitante, Paciente, Atendimento,
  Exames, Observações) com motivo; rascunho abre no Novo Protocolo preenchido (tela de confirmação
  paralela removida). Novo Protocolo: 3b feito; "Incluso em" revertido.
- [ ] Decisões a confirmar: sentido de CREDIT/DEBIT (assumido: DEBIT = clínica deve mais); aviso extra
  ao corrigir fechamento já faturado (hoje só auditoria).
- [ ] Preço de exame incluído depois: o catálogo tem um preço com janela de vigência, sem histórico;
  fora da janela a inclusão é recusada ("sem preço vigente").
- [x] Grade de exames na edição mostra o preço do snapshot do exame já lançado.
- [x] "Corrigir cadastro" no bloco Paciente abre o formulário do paciente (exige `patients.manage`; vale para todos os atendimentos dele).
- [x] Artefato de validação atualizado para o modelo real (ajuste no próprio fechamento).
- [x] Axe + overflow em desktop/tablet/mobile (`e2e/attendance-correction.spec.ts`): detalhe, cada editor de bloco e modal do paciente.

## Transversais
- [x] 401 no console era a checagem anônima GET /auth/me da tela de login (esperado).
- [x] 422 de prévia após confirmar atendimento: corrigido (prévia não é refeita depois de confirmar).
- [ ] Teste de frontend intermitente já visto uma vez (passou em 3 reexecuções), não diagnosticado.
- [ ] Seta do dropdown de Clínica apareceu meio girada numa captura (provável animação); confirmar.
- [ ] Logs da plataforma Vercel podem conter query string (fora do filtro do uvicorn).
- [ ] QA exploratório completo de Veterinários, Pacientes, Exames, Usuários e Fechamento.

## QA exploratório de Pacientes e Veterinários (19/11)
Feito contra API e navegador reais (PostgreSQL 17 descartável, backend, Vite, Playwright). Corrigidos
nesta rodada, cada um com teste de regressão: texto livre sem trim/limite em Pacientes e
Veterinários (nome em branco e de 5000 caracteres eram gravados); CRMV só de espaços derrubava a
API com 500; e-mail de veterinário sem formato; enumeração de usuário por tempo no login
(argon2 só para conta existente); duplo clique em "Salvar" criava dois pacientes; lista de pacientes
mostrava erro de API como "Nenhum paciente encontrado."; tela de pacientes inutilizável no celular
(formulário espremido em ~70 px).

Abertas (não bloqueantes):
- [ ] Lista de veterinários mostra a mesma mensagem genérica para 403 e para falha de rede; a regra
      de frontend pede 401 e 403 distintos.
- [x] Formulário de paciente no celular: "Nome do paciente" ocupa só metade da linha.
      RESOLVIDO (fatia 5): cadastro em coluna única no mobile, nome em largura total.
- [ ] Decidir se está certo: editar paciente INATIVO é aceito (200) e mover paciente para outra
      clínica via PATCH também; hoje não há bloqueio nem aviso.
- [ ] Isolamento por clínica não foi exercitado: os papéis de clínica (CLINIC_ADMIN, CLINIC_STAFF,
      VETERINARIAN) não têm nenhuma permissão semeada, então todo endpoint de pacientes/veterinários
      responde 403 para eles. Segue valendo o bloqueador de tenant do HANDOFF.
- [ ] Bloqueio por tentativas é por login (5 falhas): quem erra a senha de outra pessoa trava a conta
      dela (efeito esperado do desenho; registrar a decisão).
- [x] Atualização de paciente (PATCH) não tem o guard de duplo envio; o `row_version` impede dano.
      RESOLVIDO (fatia 5): os formulários de bloco usam `useSubmitGuard`.
- [ ] Não verificado: menu lateral para o papel TECHNICAL (a leitura devolveu lista vazia), fluxo só
      por teclado, telas de detalhe com XSS, e leitura por leitor de tela (o `getByRole` do Playwright
      não achou o "Salvar" do formulário de paciente, embora o DOM e o Chromium o mostrem).
- [ ] Item 13 (zip bomb) não se aplica: pacientes e veterinários não têm upload.

Ressalvas da revisão independente (19/11), não bloqueantes:
- [ ] **Dado legado acima dos novos limites** (auditor): colunas de texto de `patients` e
      `veterinarians` não têm tamanho. Se a planilha importada tiver `owner_phone`/`owner_document`
      > 30, `breed`/`age_description` > 100 ou e-mail fora do formato, a edição daquele registro
      devolve 422 até corrigir o campo. Antes de produção, conferir no banco importado com
      `max(length(...))` e `email !~ regex`; se houver violadores, ampliar o limite ou limpar por
      revisão. Falta um teste de integração com linha legada acima do limite.
- [ ] `notes`, `phone`, `owner_phone` e `owner_document` aceitam `""` (não viram `NULL`) e `notes`
      não é aparado; e-mail `""` na API agora dá 422 (o frontend já envia `null`). Documentar no
      contrato ou normalizar.
- [ ] Duplo clique só tem teste na página de pacientes; a seção de paciente do Novo Protocolo e o
      modal de criação usam o mesmo hook, mas não têm teste próprio. "Esqueci a senha" não tem
      teste dedicado (verificado só visualmente e no QA).
- [ ] Login: o tempo do ramo "usuário inexistente" e do ramo válido ainda difere por ruído (queries
      de sessão e papel); endurecer só se o risco justificar.
- [ ] O subagente `qa-fatia` (`.claude/agents/qa-fatia.md`) só vira tipo de agente depois de recarregar
      a sessão; nesta rodada o QA independente rodou como agente genérico seguindo esse arquivo.

## Pacientes: regra de domínio e backend (fatia 3, 19/11)
Decisão do usuário: paciente INATIVO só reativa; trocar a clínica exige motivo e grava antes/depois na
auditoria; atendimentos antigos não mudam (guardam a própria `clinic_id`). Implementado: `POST
/patients/{id}/reactivate`, PATCH de inativo = 409, `reason` na troca de clínica, filtro `species_id`,
`clinic_id` combinado com o escopo do ator, `GET /patients/summary`. Ressalvas da revisão, não bloqueantes:
- [ ] Teste de integração (HTTP, PostgreSQL) com ator de ESCOPO CLÍNICA: PATCH com destino fora do
      escopo (404), `reactivate` de paciente de outra clínica (404), `/summary` com `clinic_id` de outra
      clínica (zeros) e 403 sem `patients.read`. Hoje só há teste unitário com fakes; depende de um papel
      de clínica com permissão (fatia 6 do plano).
- [x] Concorrência (lost update) CORRIGIDA nesta fatia: `save()` gravava `row_version + 1` sem conferir a
      versão do banco, então dois PATCH com a mesma `expected_row_version` davam 200 e 200 (reproduzido pelo
      QA em servidor real, 3 de 3 rodadas). Agora `save()` lê a linha com `FOR UPDATE`, compara a versão e
      levanta `ConflictError`; update, desativar e reativar pedem `get_by_id(..., for_update=True)`.
      Antes `[200, 200]`, depois `[200, 409]` nas mesmas 3 rodadas; teste determinístico em
      `tests/integration/test_patients_repository.py` (falha sem a correção). O mesmo padrão deve ser
      conferido nos outros repositórios que fazem `session.get` + `row_version + 1` (clínicas,
      veterinários, catálogo, identidade) — o HANDOFF já listava a fatia "`row_version` transversal".
- [ ] `confirm_attendance` não trava a linha do paciente: uma troca de clínica entre a leitura e o commit
      da confirmação deixaria o atendimento (íntegro, com a própria clínica) ligado a paciente já em outra
      clínica. Risco baixo; mesmo conserto (lock) se for relevante.
- [ ] Rascunho de atendimento aberto cujo paciente mudou de clínica passa a falhar na prévia e na
      confirmação ("Paciente não pertence à clínica do atendimento"): seguro, mas pode estranhar; avisar
      na tela de troca de clínica (fatia 5).
- [ ] `reason` é texto livre e vai para o `audit_log`: pode conter PII digitada; sugerir na UI não
      incluir dado pessoal e garantir que o log de aplicação não o imprima.
- [ ] `species_id` e `status` de `patients` sem índice: medir com `EXPLAIN` antes de criar.
- [x] O formulário de edição atual desabilita a clínica, então paciente LEGADO sem clínica não ganha uma
      pelo formulário; resolver na tela de detalhe com blocos (fatia 5).
      RESOLVIDO (fatia 5): o bloco Clínica dá clínica ao legado sem motivo.
- [ ] `reason` enviado sem troca de clínica é descartado em silêncio (coberto por teste unitário).
- [ ] O `openapi.json` desta fatia inclui também os limites de schema da rodada anterior, que não tinham
      sido regenerados (`npm run api:check` falharia no CI sem isso).

## Pacientes: lista no padrão Operação (fatia 4, 19/11)
A lista passou ao padrão (cartões, abas, filtros, tabela, popover) e ganhou `/pacientes/novo` e
`/pacientes/:id` (interinas, com os componentes antigos até a fatia 5). Ressalvas do QA e da revisão:
- [x] **Backend, transversal (achado do QA):** `search` com byte NUL (`%00`) devolve 500 (`psycopg.DataError:
      PostgreSQL text fields cannot contain NUL`) em `/patients`, `/veterinarians` e `/clinics`. Validar o
      parâmetro (tipo compartilhado `SearchQuery` sem NUL e com tamanho máximo) e devolver 422.
      RESOLVIDO (rodada fix/search-validation-and-list-cleanup): tipos `SearchQuery`/`ProtocolQuery`/`OwnerNameQuery`/`ReasonQuery` e rede para NUL em corpo; ver a seção abaixo.
- [x] Erro ao inativar/reativar (409, 403, rede) não aparece para o usuário nas listas de Pacientes e de
      Veterinários; mostrar alerta ou toast.
      RESOLVIDO: hook `useActionError`; alerta na lista e dentro do popover (pacientes e clínicas).
- [x] DRY: `displayValue` existe em 4 lugares (`patient-labels.ts`, `clinic-detail.tsx`,
      `veterinarian-detail-page.tsx`, `veterinarian-row-popover.tsx`) e o CSS de tabela de cadastro em 3
      (`patient-table.css`, `veterinarian-table.css`, `clinic-table.css`, incluindo regras globais
      `tr[data-selectable]`). Extrair para `shared/lib` e um `registry-table.css`; deve ser a primeira
      tarefa da próxima tela de cadastro.
      RESOLVIDO: `displayValue` em `shared/lib/formatters` e `shared/ui/registry-table.css` (regras de seleção escopadas).
- [x] Rodapé de paginação mostra "Nenhum paciente ‹ 1 / 1 ›" durante carregamento, lista vazia e erro
      (componente compartilhado da Operação; igual em Veterinários).
      RESOLVIDO: sem itens não há rodapé.
- [ ] Inativar numa aba de status, estando na página N, pode deixar a página vazia com `total` > 0.
- [ ] No mobile as colunas Clínica e Idade ficam só no popover (igual a Veterinários); a tabela rola
      dentro do painel.
- [x] O detalhe interino `/pacientes/:id` não quebra nome/tutor de 200 caracteres (fatia 5 refaz).
      RESOLVIDO (fatia 5): título, cartões e blocos quebram linha.
- [ ] O `getByRole('button', { name: 'Cancelar' })` do Playwright não achou o botão do formulário de
      paciente embora o DOM e o jsdom o encontrem (mesma limitação de seletor já vista com "Salvar").

## Rodada de limpeza: busca com NUL, erro de ação, tabelas e rodapé (19/11)
Corrigido: byte NUL em `search`/`protocol_number`/`owner_name`/`reason` agora dá 422 no campo; NUL em
campo de corpo dá 422 pela rede de `DataError` (restrita a texto: NUL e SQLSTATE 22021/22P05); o resto
da classe 22 segue 500 com o SQLSTATE logado, para não culpar o cliente por um total que o servidor
calculou. `search` aceita até 254 caracteres (e-mail de usuário). Abertas, não bloqueantes:
- [x] **Entradas numéricas sem limite** (auditor): `quantity` de item de atendimento (`ge=1`, sem `le`),
      `age_value` e os campos de dinheiro enviados pelo cliente podem estourar a coluna e viram 500
      (22003). Definir limites de domínio (decisão de produto) e uma exceção de domínio para estouro de
      total no confirmar/fechar, com teste no limite (`12-attendance.md`, `13-monthly-closure.md`).
      PARCIAL (rodada de pendências 19/11): limites decididos com o usuário — quantidade 1–999 e preço/taxa até R$ 99.999,99 (`shared/domain/limits.py`, `api/field_types.py`), desconto limitado a 14 dígitos; testes no limite. Segue aberto: `age_value` e a exceção de domínio para total estourado no fechar (não alcançável com os tetos atuais).
- [x] **Importação com NUL** (auditor): CSV de exames (`csv.DictReader` aceita NUL) e planilha (`raw_data`
      JSONB recusa `\u0000`) derrubam o lote inteiro com 422 genérico, sem a linha. Rejeitar NUL por linha
      e registrar status de erro (`10-data-migration.md`: toda linha tem estado final); testar célula com NUL.
      RESOLVIDO: CSV de exames rejeita NUL e preço acima do limite/não finito por linha (teste). Planilha .xlsx com NUL já é recusada como arquivo inválido pelo leitor (XML não carrega NUL), antes de qualquer staging (teste).
- [ ] NUL em campo de corpo responde 422 genérico sem indicar o campo; aplicar `reject_nul` nos tipos de
      texto dos schemas daria a mensagem por campo.
- [x] Confirmar se o registro de idempotência fica em transação própria: um 4xx no meio do caso de uso
      poderia deixar a chave "em andamento".
      RESOLVIDO: `test_a_failed_confirm_does_not_burn_its_idempotency_key` mostra que a falha desfaz o registro e a mesma chave funciona depois.
- [x] Busca no servidor não ignora acento: `joao` não acha `João` (a lista local ignora; o SQL não).
      RESOLVIDO: migration 0044 (`unaccent`) + `folded()`/`fold()`; vale para pacientes, clínicas, veterinários, usuários, exames, categorias e tutor em atendimentos. Índice trigram fica para quando houver volume medido.
- [ ] A lista de veterinários não quebrava CRMV/e-mail de 5000 caracteres (dado legado de antes dos limites):
      CRMV agora trunca; conferir e-mail.
- [ ] `frontend/test-results` ficou com artefatos de falha do Playwright (ignorado pelo git); apagar à mão.
- [ ] Teste do `confirm` de atendimento com quantidade enorme (faltou payload válido no QA).

## Pacientes: detalhe e cadastro em blocos (fatia 5, 19/11)
`/pacientes/:id` virou blocos editáveis (Identificação, Tutor, Clínica com motivo, Observação) e
`/pacientes/novo` usa o layout do Novo Protocolo. Corrigidos depois da revisão e do QA: motivo da troca
de clínica validado em 500 caracteres; "Recarregar" após 409 volta o bloco à leitura (antes deixava o texto
digitado para um novo Salvar sobrescrever); bloco aberto volta à leitura quando o paciente é inativado;
clínica atual inativa continua no dropdown; falha 500 do detalhe não diz "não encontrado"; foco do teclado
vai ao primeiro campo ao abrir e volta ao "Editar" ao fechar. Abertas, não bloqueantes:
- [x] **DRY e camada:** `shared/ui/detail-block.tsx` importa CSS de `features/attendances` (as classes
      `attendance-correction-block__*` e `attendance-readonly-detail__*`). Extrair `shared/ui/detail-block.css`
      com nomes `detail-block__*` e migrar o detalhe de Veterinários e o de atendimento para o `DetailBlock`
      (Veterinários ainda tem a cópia `veterinarian-detail-block.tsx`).
      PARCIAL: o CSS saiu de `features/attendances` para `shared/ui/readonly-detail.css` e `correction-block.css` (sem inversão de camada). Renomear as classes para `detail-block__*` e migrar Veterinários/atendimento para o `DetailBlock` segue aberto.
      RESOLVIDO: Veterinários, Exames e Atendimento usam o `DetailBlock`/`BlockFooter` compartilhado (cópias removidas, -310 linhas). Os nomes das classes CSS seguem `attendance-*` (renomear é cosmético).
- [x] O `audit_log` de `patients.updated` guarda só nome, status e `clinic_id` (e o motivo na troca de clínica);
      não registra quais campos mudaram (telefone, observação, raça, espécie, idade). Decidir o que auditar
      (cuidado com PII de tutor) e gravar antes/depois dos campos alterados.
      RESOLVIDO: grava só os campos alterados (antes/depois), quem e quando; telefone e documento do tutor registram só "[alterado]" (PII).
- [x] `create-patient-modal.tsx` não é usado em nenhum lugar (código morto, achado do QA): apagar ou
      reaproveitar. `PatientForm` segue só no "Corrigir cadastro" de atendimento; migrar para os blocos
      ou para o formulário de criação na fatia de atendimento.
      RESOLVIDO: arquivo e CSS removidos. `PatientForm` continua no Corrigir cadastro do atendimento.
- [ ] Teclado em tablet/mobile, contraste medido do foco, IDOR entre escopos de clínica e grep de PII no
      log não foram executados no QA desta fatia (fatia 6 trata o isolamento).
- [ ] Um teste de teclado de Veterinários (tablet) falhou uma vez no run completo e passou isolado e 9 de 9
      repetido (`veterinarians.spec.ts:230`, `toHaveCount` logo após Esc): provável corrida; estabilizar.


## Rodada de pendências (19/11)
Teste de prévia do fechamento (`closure-page.test.tsx`) falhava 1 em 3 por o estado "Carregando" durar 50 ms;
atraso do mock subiu para 500 ms (4 de 4 verdes). Abertas e dependentes de decisão: o que auditar nos campos do
paciente (PII do tutor) e a correção transversal de `row_version` (catálogo, clínicas, identidade, veterinários).
Ressalvas da revisão e do QA desta rodada, não bloqueantes (dono: backend, próxima rodada de API):
- [x] 405 (método não permitido) responde `error.code = "INTERNAL_ERROR"` (ex.: GET em `/on-call-fee-settings/NORMAL`):
      mapear `HTTPException` 4xx para código estável (`METHOD_NOT_ALLOWED`) no handler de erros.
      RESOLVIDO: código estável `METHOD_NOT_ALLOWED` (teste).
- [x] `fold()` (NFD) não cobre ø, đ, ł, ß, æ que o `unaccent` do Postgres mapeia; irrelevante para nomes em
      português. Se aparecer, aplicar `unaccent(:termo)` no SQL em vez de dobrar em Python.
      RESOLVIDO: o termo é dobrado no banco (`folded_pattern`), simétrico com a coluna; teste com ø/ł.
- [ ] Índice de busca: `unaccent` é STABLE; um índice trigram exigirá wrapper IMMUTABLE em migration própria,
      só quando houver volume medido (hoje varredura sequencial, igual ao `lower(col) LIKE` anterior).
- [x] Migration 0044: o `downgrade` remove a extensão mesmo se um DBA a criou antes; confirmar no runbook de
      deploy que o papel da migration tem `CREATE` no banco e a versão do Postgres de produção (>= 13).
      RESOLVIDO: downgrade é no-op documentado (a extensão permanece). Segue valendo confirmar no runbook o privilégio CREATE e Postgres >= 13.
- [x] Antes do deploy rodar `SELECT max(price_base) FROM exams` e `max(fee_amount)` nas taxas: valor legado acima de
      R$ 99.999,99 impediria reenviar o valor em edição (422).
      EXECUTADO no banco de QA (sintético): máximos 99.999,99 (valores de teste no teto), taxas de plantão 150,00. O mesmo SELECT ainda precisa rodar no banco real antes do deploy.
- [x] `age_value` do paciente segue sem teto numérico (dono: cadastro de pacientes, próxima fatia de pacientes).
      RESOLVIDO: teto 999 (teste); openapi regenerado.
- [x] Teste de prévia do fechamento ainda depende de tempo (delay 500 ms); trocar por promise controlada.

      RESOLVIDO: promise controlada em vez de timer.

## Fatia 6: isolamento por clínica, teclado, menu e acessibilidade (19/11)
Primeira execução real com um papel de escopo clínica (perfil criado com `users.*`). Dados de negócio (pacientes,
atendimentos, fechamentos, clínicas, filtros, buscas, contagens) estavam isolados. Falhas de governança achadas e
CORRIGIDAS nesta fatia, com testes de integração (`test_clinic_scope_isolation_api.py`): usuário de clínica listava,
ativava, desativava e mudava papel/acesso de usuários de outra clínica e do laboratório; vinculava a si um
veterinário invisível; criava veterinário vinculado a outra clínica. Regra agora: alvo só alcançável se tem vínculo
ativo apenas com clínicas do ator (fora disso 404); ator de clínica nunca atribui papel de laboratório.
Corrigidos também: barra lateral fechada no mobile saía da tela mas continuava na ordem de Tab (agora `visibility`);
linhas de Operação tinham `aria-haspopup`/`aria-expanded` inválidos em `tr` (axe serious); busca de Operação sem rótulo.
Abertas (nenhuma bloqueia release; dono: frontend/UX salvo indicação):
- [x] (resolvido: menu filtrado por `*.read` e 403 com mensagem de permissão em Clínicas/Veterinários; resta o formulário de novo exame sem `catalog.manage`) **Menu lateral não filtra por permissão** (só Usuários e Fechamento): TECHNICAL/RECEPTION/FINANCE veem itens que
      abrem "Não foi possível carregar" (403 tratado como erro genérico em Clínicas e Veterinários). Filtrar o menu por
      `*.read` e tratar 403 com a mensagem de permissão, como Pacientes já faz. `/cadastros/exames/novo` abre o formulário
      sem `catalog.manage` (o backend recusa ao salvar).
- [ ] `document.title` é "Vertere Lab" em toda rota (WCAG 2.4.2); sem skip-link; foco vai ao `BODY` após navegar.
- [ ] "Carregando…" e estados vazios não são regiões vivas (`role=status`/`aria-busy`); erro de lista de pacientes sem
      "Tentar novamente"; `svg` sem `aria-hidden` no Login e no Novo Protocolo.
- [ ] Esc não cancela a edição de um bloco; menu "Ações" não move o foco para dentro nem responde a setas.
- [ ] Campos de texto têm `outline: none` (anel só no wrapper `:focus-within`): confirmar com captura focada de cada tipo.
- [ ] Novo Protocolo: a busca do histórico lista pacientes de outras clínicas (o backend recusa com 422; a UI deveria
      filtrar pela clínica escolhida e explicar); rascunhos órfãos ao abandonar a tela; opções do seletor de paciente
      não respondem a seta+Enter.
- [ ] Não existe endpoint de leitura do `audit_log` nem de owners: a auditoria não é consultável pela API (decidir se
      entra no roadmap de relatórios).
- [ ] Não executados: leitor de tela real; estado de carregamento por rede lenta real; contraste do anel sobre a barra lateral.
Achados do auditor na correção da fatia 6 (ressalvas abertas; os dois bloqueantes foram corrigidos e testados: ator de clínica
só concede papel de clínica com permissões contidas nas suas e nunca altera o próprio acesso; perfis de acesso só pelo
laboratório e leitura limitada a perfis de clínica):
- [x] **Política aplicada (a confirmar pelo produto):** ator de clínica só altera ou desativa veterinário cujos vínculos são todos com
      clínicas dele (403 se compartilhado ou sem vínculo), não muda `is_autonomous`, não cadastra autônomo e não vincula veterinário
      que ainda não tem clínica; laboratório sem restrição. Teste em `test_clinic_scope_isolation_api.py`.
      Ressalvas tratadas: (1) TOCTOU: update, desativar, vincular, desvincular e o lote de vínculos agora seguram o lock da
      linha do veterinário (`get_by_id_for_update`; teste `test_veterinarian_row_lock.py`); (2) o 403 de "sem clínica"
      explica que só o laboratório vincula de novo; (3) 409 de CRMV duplicado: ACEITO de propósito, pois o CRMV é número
      de registro profissional único e a restrição de unicidade só existe se avisar o conflito; não é segredo, e o 409 não
      devolve nenhum outro dado do veterinário.
      Texto original: veterinário autônomo é visível a todo ator de clínica (`visibility.py`), então uma clínica B pode
      editar, desativar ou vincular a si um autônomo da clínica A.
      Reverificado no app (QA, 19/11): também vale para veterinário COMPARTILHADO entre A e B (ator da A edita o nome e desativa
      o veterinário que a B também usa; os vínculos da B ficam protegidos) e o PATCH de um autônomo sobrescreve `is_autonomous`. Definir a política (ex.: ator de clínica só muta autônomo
      sem vínculos ou com vínculo a clínica própria).
- [ ] TOCTOU em ativar/desativar/papel: o escopo do alvo é checado sem lock nem `expected_row_version` (acessar e trocar vínculo
      do alvo entre a checagem e a escrita). Usar `SELECT ... FOR UPDATE` do usuário (junto da fatia "row_version transversal").
- [ ] `create_user` responde 409 de e-mail já cadastrado antes de qualquer escopo (enumera e-mails entre clínicas).
- [ ] Cobertura a ampliar: vínculo inativo/revogado, usuário sem vínculo, `search`/`total` com escopo em testes de integração.

