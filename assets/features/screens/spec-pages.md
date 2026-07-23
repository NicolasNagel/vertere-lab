# Tela de Login

## Objetivo

Autenticar usuários internos e direcioná-los para a área autorizada.

## Campos

- Identificador do usuário:
  - obrigatório;
  - pode aceitar e-mail ou nome de usuário;
  - remover espaços laterais.
- Senha:
  - obrigatória;
  - mascarada por padrão.
- Manter conectado:
  - opcional;
  - não deve armazenar senha no navegador.

## Ações

- Entrar no sistema.
- Mostrar ou ocultar senha.
- Recuperar senha.
- Solicitar ajuda ao administrador.

## Estados

- Inicial.
- Enviando.
- Credenciais inválidas.
- Usuário inativo.
- Usuário bloqueado.
- Falha de conexão.
- Autenticação concluída.
- Sessão expirada.

## Permissões

A tela é pública.

## Integração esperada

POST /api/v1/auth/login

Request:
- login
- password
- remember_me

Response:
- usuário autenticado;
- sessão;
- permissões efetivas.

## Critérios de aceite

- Não conter usuário ou senha preenchidos no código.
- Permitir envio pelo teclado.
- Desabilitar o botão durante a requisição.
- Exibir erros sem revelar se um usuário específico existe.
- Redirecionar usuários autenticados.
- Funcionar em desktop, tablet e celular.

---

# Tela de Dashboard

## Objetivo

Dar uma visão geral do dia operacional do laboratório e permitir acesso rápido às ações mais frequentes.

## Campos

Somente dados de leitura (sem formulário):

- Saudação com nome do usuário logado.
- Data corrente.
- KPIs: protocolos hoje, laudos pendentes, amostras em coleta, faturado no mês.
- Lista de atividade recente (últimos eventos de protocolos/laudos).
- Ranking de exames mais pedidos no período.
- Alerta de laudos vencendo.

## Ações

- Abrir novo protocolo.
- Ver todos (atividade recente) → navega para Operação.
- Clicar em um item de atividade → abre o protocolo/laudo correspondente.
- Clicar no alerta de vencimento → abre o protocolo citado.

## Estados

- Carregando.
- Carregado com dados.
- Carregado sem atividade no dia (estado vazio).
- Falha ao carregar KPIs (mostrar erro parcial sem quebrar a tela).
- Sem permissão para ver valor faturado (oculta o KPI financeiro, mantém os demais).

## Permissões

- Visível para todos os perfis internos autenticados.
- KPI "Faturado / mês" exige `VIEW_EXAM_PRICES`.
- Alertas e atividade recente respeitam o mesmo escopo de dados do perfil (ex.: recepção não vê valores dentro da atividade).

## Integração esperada

GET /api/v1/dashboard

Response:
- today_protocols_count
- pending_laudos_count
- in_collection_count
- billed_month_cents (omitido se sem permissão)
- top_exams: [{ exam_name, count }]
- recent_activity: [{ type, protocol_number, patient_name, clinic_name, vet_name, exam_name, occurred_at }]
- expiring_laudos: [{ protocol_number, patient_name, due_at }]

## Critérios de aceite

- Carregar em uma única requisição (ou paralelizar sem bloquear o primeiro paint).
- Atualizar KPIs sem exigir reload manual da página (revalidação ao focar a aba).
- Não exibir valores monetários para perfis sem permissão, em nenhum ponto da tela.
- Funcionar em desktop, tablet e celular (empilhar KPIs em telas estreitas).

---

# Tela de Operação · Registro de Atendimentos

## Objetivo

Listar, buscar e filtrar todos os protocolos abertos no laboratório, servindo como ponto central de acompanhamento operacional.

## Campos

Filtros (não é formulário de cadastro):

- Busca livre: protocolo, paciente ou tutor.
- Status: todos, aguardando coleta, em análise, laudo pendente, concluído.
- Período (mês/intervalo de datas).
- Clínica.
- Tipo de atendimento (normal/plantão).

## Ações

- Abrir novo protocolo.
- Buscar/filtrar (aplicação incremental, sem precisar de botão "buscar").
- Abrir detalhe de um protocolo.
- Baixar PDF do protocolo (menu de linha).
- Cancelar protocolo (menu de linha, com confirmação).
- Paginar / carregar mais.

## Estados

- Carregando lista.
- Lista com resultados.
- Lista vazia (nenhum protocolo no filtro atual).
- Erro ao carregar.
- Gerando PDF (por linha, enquanto o job roda).
- PDF pronto para download.
- Falha ao gerar PDF.

## Permissões

- Coluna "Valor" e ação de PDF com valores exigem `VIEW_EXAM_PRICES`.
- Cancelar protocolo exige `PROTOCOL_DELETE`.
- Demais visualizações liberadas para qualquer perfil interno autenticado.

## Integração esperada

GET /api/v1/protocols

Request (query params):
- status
- clinic_id
- vet_id
- date_from, date_to
- search
- cursor, limit

Response:
- items: [{ id, number, opened_at, clinic_name, vet_name, patient_name, patient_species, patient_age, exams: [exam_name], attendance_type, status, total_cents }]
- next_cursor

POST /api/v1/protocols/{id}/pdf
Response: { job_id }

GET /api/v1/protocols/{id}/pdf/status?job_id=...
Response: { status, download_url?, file_name? }

POST /api/v1/protocols/{id}/cancel
Request: { reason }

## Critérios de aceite

- Filtros combináveis (status + período + clínica ao mesmo tempo).
- Não perder o filtro aplicado ao paginar.
- Nome do arquivo de PDF seguir o padrão `P<numero>-<ano>_<exames>_<paciente>.pdf`.
- Ocultar coluna de valor completamente (não só mascarar) para quem não tem permissão.
- Funcionar em desktop, tablet e celular (tabela com scroll horizontal em telas estreitas).

---

# Tela de Novo Protocolo

## Objetivo

Registrar a abertura de um novo protocolo de exame, vinculando clínica, veterinário, paciente, exames solicitados e forma de atendimento.

## Campos

- Clínica solicitante:
  - obrigatório;
  - selecionável a partir do cadastro de clínicas.
- Veterinário responsável:
  - obrigatório;
  - lista filtrada pela clínica selecionada (ou lista de autônomos);
  - exibe CRMV e contato como apoio.
- Paciente:
  - nome: obrigatório;
  - espécie: obrigatório, selecionável;
  - sexo: obrigatório;
  - raça: opcional;
  - idade: opcional;
  - tutor/proprietário: obrigatório;
  - opção de buscar paciente já existente no histórico.
- Exames:
  - seleção múltipla a partir do catálogo;
  - obrigatório ao menos 1 exame;
  - preço vem do catálogo, não editável neste campo.
- Tipo de atendimento:
  - obrigatório;
  - normal ou plantão.
- Método de coleta:
  - obrigatório;
  - selecionável (motoboy, uber, outros cadastrados).
- Desconto:
  - opcional;
  - valor monetário.
- Observações:
  - opcional;
  - texto livre.

## Ações

- Adicionar/remover exame da lista selecionada.
- Alternar tipo de atendimento (recalcula valor com taxa de plantão).
- Selecionar método de coleta.
- Abrir protocolo (submissão).
- Cancelar (descarta o formulário).

## Estados

- Preenchimento inicial (vazio).
- Preenchendo (validação incremental por campo).
- Nenhum exame selecionado (bloqueia submissão).
- Enviando.
- Protocolo aberto com sucesso (mostra número gerado).
- Falha ao abrir (ex.: conflito de numeração, erro de rede).

## Permissões

- Ação exige `PROTOCOL_CREATE`.
- Edição manual do valor total exige `EDIT_VALUE_MANUAL` (campo/ação ocultos sem essa permissão).
- Visualização de preços por exame exige `VIEW_EXAM_PRICES`; sem essa permissão, exames aparecem selecionáveis mas sem valor visível, e o resumo de valor total fica oculto.

## Integração esperada

GET /api/v1/clinics?active=true
GET /api/v1/veterinarians?clinic_id=...
GET /api/v1/exams?active=true
GET /api/v1/patients?search=...

POST /api/v1/protocols

Request:
- clinic_id
- veterinarian_id
- patient_id (ou objeto de paciente novo)
- exam_ids: []
- attendance_type
- collection_method
- collection_scheduled_at (opcional)
- discount_cents (opcional)
- observations (opcional)

Response:
- protocol_number
- protocol_id
- total_cents
- status

## Critérios de aceite

- Número de protocolo gerado pelo servidor, nunca calculado no cliente.
- Não permitir dois exames idênticos duplicados na mesma seleção.
- Recalcular valor total automaticamente ao mudar exames, desconto ou tipo de atendimento.
- Impedir submissão sem paciente, clínica, veterinário e ao menos 1 exame.
- Funcionar em desktop, tablet e celular (formulário reflui em coluna única em telas estreitas).

---

# Tela de Preenchimento de Laudo

## Objetivo

Permitir que o patologista registre os resultados de um exame, revise valores fora da referência e assine o laudo para liberação ao solicitante.

## Campos

- Resultado por parâmetro (ex.: hemácias, hemoglobina, hematócrito):
  - obrigatório para assinatura;
  - numérico, respeitando casas decimais do parâmetro;
  - comparado automaticamente à faixa de referência.
- Observações e conclusão:
  - opcional para rascunho;
  - obrigatório para assinatura.

## Ações

- Alternar entre exames do mesmo protocolo (abas).
- Salvar rascunho (manual ou automático).
- Aceitar sugestão do assistente clínico (preenche observações).
- Assinar e enviar laudo.
- Pré-visualizar PDF.
- Consultar histórico do paciente (exames anteriores).

## Estados

- Carregando laudo.
- Rascunho vazio.
- Rascunho em edição (autosave pendente).
- Rascunho salvo.
- Parâmetro fora da referência (destaque visual, sem bloquear).
- Assinando.
- Assinado (somente leitura a partir daqui).
- Falha ao salvar/assinar.
- Conflito de edição concorrente (outro usuário editando o mesmo laudo).

## Permissões

- Visualizar laudo exige `LAUDO_VIEW`.
- Preencher/editar exige `LAUDO_FILL`.
- Assinar exige `LAUDO_SIGN`.
- Reabrir laudo assinado (correção) exige perfil Master.

## Integração esperada

GET /api/v1/protocols/{id}
GET /api/v1/protocol-exams/{id}/laudo

Response:
- results: { parameter_key: value }
- flags: { parameter_key: 'NORMAL' | 'BAIXO' | 'ALTO' }
- conclusion
- draft_saved_at
- signed_by, signed_at (se assinado)

PATCH /api/v1/laudos/{id}/draft
Request: { results, conclusion }

POST /api/v1/laudos/{id}/sign
Response: { signed_at, signed_by, pdf_job_id }

GET /api/v1/patients/{id}/timeline

## Critérios de aceite

- Cálculo de flag (normal/baixo/alto) feito no servidor, não no cliente.
- Autosave não deve sobrescrever edição concorrente sem aviso.
- Bloquear edição de campos após assinatura.
- Exibir claramente qual exame da aba está sendo visualizado quando o protocolo tem múltiplos.
- Funcionar em desktop e tablet (uso majoritariamente interno, mobile não é prioridade nesta tela).

---

# Tela de Cadastro de Exames & Preços

## Objetivo

Manter o catálogo de exames oferecidos pelo laboratório, com preços, categorias, espécies atendidas e adicional de plantão.

## Campos

- Código do exame:
  - obrigatório;
  - único.
- Nome:
  - obrigatório.
- Descrição:
  - opcional.
- Categoria:
  - obrigatório;
  - selecionável entre categorias cadastradas.
- Preço base:
  - obrigatório;
  - valor monetário maior que zero.
- Adicional de plantão:
  - opcional;
  - percentual ou valor fixo.
- Espécies atendidas:
  - obrigatório ao menos 1;
  - seleção múltipla.
- Ativo/inativo:
  - obrigatório;
  - padrão ativo.

## Ações

- Criar novo exame.
- Editar exame existente.
- Inativar exame (soft delete, não remove histórico).
- Importar catálogo via CSV.
- Filtrar por categoria e espécie.
- Buscar por nome/código.

## Estados

- Lista carregando.
- Lista vazia (sem exames cadastrados).
- Formulário de criação/edição aberto.
- Salvando.
- Salvo com sucesso.
- Erro de validação (ex.: código duplicado).
- Importação de CSV em progresso.
- Importação concluída com relatório de erros/linhas ignoradas.

## Permissões

- Visualizar exige `EXAM_VIEW`.
- Criar/editar/inativar exige `EXAM_EDIT`.
- Preço só é exibido para quem tem `VIEW_EXAM_PRICES` (mesmo com `EXAM_VIEW`).

## Integração esperada

GET /api/v1/exams?category=&species=&search=&active=

POST /api/v1/exams
Request: { code, name, description, category, price_cents, plantao_surcharge_cents, plantao_surcharge_percent, species, active }

PATCH /api/v1/exams/{id}
DELETE /api/v1/exams/{id}  (soft delete)

POST /api/v1/exams/import
Request: multipart CSV
Response: { imported_count, errors: [{ line, message }] }

## Critérios de aceite

- Alterar preço de um exame não deve alterar o valor de protocolos já fechados (preço é congelado no momento do pedido).
- Impedir código duplicado.
- Importação de CSV deve reportar linha e motivo de cada erro, sem interromper as linhas válidas.
- Funcionar em desktop e tablet.

---

# Tela de Cadastro de Clínicas

## Objetivo

Manter o cadastro de clínicas parceiras, seus dados de contato, endereço e veterinários vinculados.

## Campos

- Nome da clínica:
  - obrigatório.
- CNPJ:
  - opcional;
  - único quando informado.
- Telefone:
  - opcional.
- E-mail:
  - opcional.
- Endereço:
  - CEP: opcional;
  - rua, número, bairro, cidade, UF: opcional, preenchíveis manualmente ou via busca de CEP;
  - complemento: opcional.
- Status:
  - obrigatório;
  - ativo, inativo, negativado ou especial (ex.: grupo autônomos).
- Observação:
  - opcional.

## Ações

- Criar nova clínica.
- Editar clínica.
- Inativar clínica.
- Vincular/desvincular veterinário.
- Buscar clínica na lista.
- Configurar janelas de coleta que a clínica segue.

## Estados

- Lista carregando.
- Lista vazia.
- Detalhe carregando.
- Detalhe carregado.
- Salvando edição.
- Erro de validação (ex.: CNPJ duplicado).
- Sem veterinários vinculados (estado vazio no bloco de vínculos).

## Permissões

- Visualizar exige `CLINIC_VIEW`.
- Criar/editar/vincular exige `CLINIC_EDIT`.

## Integração esperada

GET /api/v1/clinics?search=&status=
GET /api/v1/clinics/{id}

POST /api/v1/clinics
PATCH /api/v1/clinics/{id}
DELETE /api/v1/clinics/{id} (soft delete)

POST /api/v1/clinics/{id}/veterinarians
Request: { veterinarian_id, primary }
DELETE /api/v1/clinics/{id}/veterinarians/{veterinarian_id}

## Critérios de aceite

- Inativar clínica não deve apagar histórico de protocolos associados.
- CNPJ, quando informado, deve ser único.
- Vínculo de veterinário deve refletir também no cadastro do veterinário (bidirecional).
- Funcionar em desktop e tablet.

---

# Tela de Cadastro de Veterinários

## Objetivo

Manter o cadastro de veterinários, sejam vinculados a clínicas ou autônomos, com seus dados profissionais e de contato.

## Campos

- Nome:
  - obrigatório.
- CRMV:
  - obrigatório;
  - único.
- Telefone:
  - opcional.
- E-mail:
  - opcional.
- Autônomo:
  - obrigatório (sim/não).
- Clínica(s) vinculada(s):
  - obrigatório se não for autônomo;
  - permite mais de uma clínica.
- Status:
  - obrigatório;
  - ativo ou inativo.
- Observação:
  - opcional.

## Ações

- Criar novo veterinário.
- Editar veterinário.
- Inativar veterinário.
- Filtrar por tipo (todos/vinculados/autônomos).
- Buscar por nome ou CRMV.

## Estados

- Lista carregando.
- Lista vazia.
- Formulário de criação/edição aberto.
- Salvando.
- Erro de validação (ex.: CRMV duplicado).

## Permissões

- Visualizar exige `VET_VIEW`.
- Criar/editar exige `VET_EDIT`.

## Integração esperada

GET /api/v1/veterinarians?type=&search=

POST /api/v1/veterinarians
Request: { name, crmv, phone, email, is_autonomous, clinic_ids, status, observation }

PATCH /api/v1/veterinarians/{id}
DELETE /api/v1/veterinarians/{id} (soft delete)

## Critérios de aceite

- CRMV deve ser único no sistema.
- Veterinário autônomo não exige clínica vinculada; veterinário não autônomo exige ao menos uma.
- Inativar veterinário não apaga protocolos já vinculados a ele.
- Funcionar em desktop e tablet.

---

# Tela de Usuários & Permissões

## Objetivo

Gerenciar usuários internos do sistema e os perfis de permissão que controlam o que cada um pode ver e fazer.

## Campos

- Convite de novo usuário:
  - e-mail: obrigatório;
  - perfil: obrigatório, selecionável entre perfis existentes.
- Edição de perfil de permissão:
  - nome do perfil: obrigatório;
  - lista de permissões: cada uma como alternável (visualizar/editar quando aplicável).

## Ações

- Convidar usuário.
- Reenviar convite.
- Alterar perfil de um usuário.
- Desativar usuário.
- Criar novo perfil de permissão.
- Editar permissões de um perfil existente.
- Salvar alterações de permissão.

## Estados

- Lista de usuários carregando.
- Usuário com convite pendente.
- Usuário ativo.
- Usuário desativado.
- Editando perfil (painel lateral aberto).
- Salvando permissões.
- Conflito: perfil em uso por outro usuário sendo editado simultaneamente (aviso, não bloqueio).

## Permissões

- Visualizar lista de usuários exige `USER_MANAGE`.
- Editar permissões de perfil exige `PERMISSION_MANAGE`.
- Esta tela, por padrão, é exclusiva do perfil Master (demais perfis não devem enxergar o item de menu).

## Integração esperada

GET /api/v1/users
GET /api/v1/permission-profiles
GET /api/v1/permission-profiles/{id}

POST /api/v1/users/invite
Request: { email, role, permission_profile_id }

PATCH /api/v1/users/{id}/role
PATCH /api/v1/users/{id}/deactivate

POST /api/v1/permission-profiles
PATCH /api/v1/permission-profiles/{id}
Request: { name, permissions: [] }

## Critérios de aceite

- Alteração de permissão em um perfil deve refletir imediatamente para todos os usuários daquele perfil.
- Não permitir que um usuário remova a própria permissão de gerenciar usuários (evitar autoexclusão do controle).
- Convite pendente deve expirar após prazo definido pelo backend.
- Funcionar em desktop e tablet.

---

# Tela de Fechamento de Cliente

## Objetivo

Consolidar todos os protocolos de uma clínica (ou veterinário autônomo) em um período, calcular o total e gerar o demonstrativo para cobrança.

## Campos

- Cliente (clínica ou veterinário autônomo):
  - obrigatório;
  - selecionável.
- Período:
  - obrigatório;
  - data inicial e final.
- Nota fiscal:
  - opcional;
  - upload de arquivo.
- Data de vencimento:
  - opcional.

## Ações

- Consolidar (buscar protocolos do período e calcular totais).
- Salvar como rascunho.
- Gerar PDF do demonstrativo analítico.
- Anexar nota fiscal.
- Enviar/disponibilizar fechamento para o cliente.
- Marcar como pago.
- Cancelar fechamento.

## Estados

- Filtros preenchidos, aguardando consolidação.
- Consolidando.
- Consolidado (rascunho, editável).
- Gerando PDF.
- Enviado (aguardando pagamento).
- Pago.
- Atrasado.
- Cancelado.
- Nenhum protocolo encontrado no período (estado vazio).

## Permissões

- Acesso à tela exige `REPORT_CLOSURE`.
- Consolidar e enviar exige perfil Financeiro ou Master.
- Visualização pelo cliente (fora desta tela, no portal externo) é somente leitura.

## Integração esperada

POST /api/v1/closures/draft
Request: { clinic_id ou veterinarian_id, period_start, period_end }
Response: { protocols: [], subtotal_cents, plantao_cents, total_cents, draft_id }

POST /api/v1/closures/{id}/consolidate
POST /api/v1/closures/{id}/analytic-pdf
Response: { job_id }

POST /api/v1/closures/{id}/invoice
Request: multipart file

POST /api/v1/closures/{id}/send
PATCH /api/v1/closures/{id}/paid
Request: { paid_at }

## Critérios de aceite

- Consolidação deve trazer todos os protocolos concluídos no período, sem duplicidade e sem omissão.
- Não permitir editar valores de protocolos já incluídos em um fechamento enviado.
- PDF do demonstrativo deve refletir exatamente os mesmos valores mostrados na tela.
- Disponibilizar o demonstrativo ao cliente somente após o envio explícito, nunca antes.
- Funcionar em desktop e tablet.

---

# Tela de Rotas & Janelas de Coleta

## Objetivo

Gerenciar as rotas de coleta, seus horários padrão e as solicitações de coleta fora da janela habitual.

## Campos

- Rota:
  - nome: obrigatório;
  - região: opcional;
  - motorista/responsável: opcional.
- Janela de horário:
  - horário: obrigatório;
  - dias da semana: obrigatório;
  - rota associada: obrigatório.
- Clínicas inscritas em cada janela:
  - seleção múltipla.
- Solicitação fora de janela (leitura + decisão):
  - clínica solicitante;
  - horário desejado;
  - motivo.

## Ações

- Criar/editar/remover rota.
- Adicionar/remover janela de horário.
- Inscrever/remover clínica de uma janela.
- Aprovar solicitação fora de janela.
- Recusar solicitação fora de janela.

## Estados

- Lista de rotas carregando.
- Janela recém-criada (destaque "nova").
- Solicitação pendente.
- Solicitação aprovada.
- Solicitação recusada.
- Nenhuma solicitação pendente (estado vazio).

## Permissões

- Acesso e edição exigem `COLLECTION_ROUTE_MANAGE` (tipicamente exclusivo do Master/operação).

## Integração esperada

GET /api/v1/collection-routes
POST /api/v1/collection-routes
PATCH /api/v1/collection-routes/{id}
DELETE /api/v1/collection-routes/{id}

POST /api/v1/collection-routes/{id}/windows
Request: { time, days_of_week }
DELETE /api/v1/collection-windows/{id}

POST /api/v1/collection-windows/{id}/subscriptions
Request: { clinic_id }
DELETE /api/v1/collection-windows/{id}/subscriptions/{clinic_id}

GET /api/v1/collection-requests?status=PENDENTE
PATCH /api/v1/collection-requests/{id}/decide
Request: { decision, note }

## Critérios de aceite

- Alteração de horário de uma janela deve propagar em tempo real para o portal das clínicas afetadas.
- Não permitir remover uma janela com clínicas ainda inscritas sem confirmação explícita.
- Aprovação/recusa de solicitação deve notificar a clínica solicitante.
- Funcionar em desktop e tablet.

---

# Tela de Painel da Clínica (Portal Conecta)

## Objetivo

Dar à clínica/veterinário uma visão geral dos seus próprios exames, consumo do mês e próxima janela de coleta disponível.

## Campos

Somente dados de leitura:

- Saudação com nome do usuário/clínica.
- KPIs: exames em andamento, laudos disponíveis, valor consumido no mês, próxima coleta.
- Lista de exames recentes com status.
- Próxima janela de coleta disponível.
- Equipe da clínica (usuários vinculados).

## Ações

- Solicitar novo exame.
- Abrir detalhe de um exame recente.
- Ver ficha de um paciente a partir da lista recente.

## Estados

- Carregando.
- Carregado com dados.
- Sem exames no período (estado vazio).
- Aviso de mudança recente na janela de coleta.
- Falha ao carregar.

## Permissões

- Toda consulta filtrada automaticamente pela clínica do usuário logado (multi-tenant); usuário nunca vê dados de outra clínica.
- Veterinário autônomo enxerga apenas os próprios protocolos, independente da clínica de origem.

## Integração esperada

GET /api/v1/portal/dashboard
Response:
- in_progress_exams_count
- available_laudos_count
- billed_month_cents
- next_collection_window
- recent_exams: [{ protocol_number, patient_name, exam_names, status }]
- team_members: [{ name, role }]

## Critérios de aceite

- Nenhuma requisição desta tela deve aceitar `clinic_id` vindo do cliente — o escopo é sempre resolvido pela sessão no servidor.
- Atualizar automaticamente quando um laudo do dia é assinado (polling ou push).
- Funcionar em desktop, tablet e celular.

---

# Tela de Solicitar Exame (Portal Conecta)

## Objetivo

Permitir que a clínica ou veterinário abra um pedido de exame diretamente pelo portal, escolhendo paciente, exames e janela de coleta.

## Campos

- Paciente:
  - obrigatório;
  - buscável no histórico da clínica ou cadastrável na hora.
- Exames:
  - obrigatório ao menos 1;
  - seleção múltipla com busca/categoria.
- Tipo de atendimento:
  - obrigatório;
  - normal ou plantão.
- Janela de coleta:
  - obrigatório;
  - selecionável entre horários padrão da clínica;
  - opção de solicitar horário fora da janela padrão, com justificativa obrigatória nesse caso.

## Ações

- Buscar paciente existente.
- Cadastrar paciente novo inline.
- Selecionar/remover exames.
- Escolher janela de coleta ou solicitar horário alternativo.
- Confirmar solicitação.

## Estados

- Preenchendo.
- Nenhum exame selecionado (bloqueia confirmação).
- Janela padrão indisponível para o horário atual (horários passados desabilitados).
- Solicitação fora de janela pendente de aprovação do laboratório.
- Enviando.
- Solicitação confirmada (protocolo aberto).
- Falha ao enviar.

## Permissões

- Ação exige que o usuário esteja autenticado como `VET_CLINICA`, `VET_AUTONOMO` ou `CLINICA_ADMIN`.
- Preço dos exames é sempre visível para o solicitante externo (ele precisa saber o que está contratando).

## Integração esperada

GET /api/v1/portal/patients?search=
GET /api/v1/portal/exams?active=true
GET /api/v1/portal/collection-windows

POST /api/v1/portal/protocols
Request: { patient_id ou novo paciente, exam_ids, attendance_type, collection_window_id ou { desired_at, reason } }

Response:
- protocol_number
- status
- total_cents
- collection_status ('CONFIRMADA' | 'AGUARDANDO_APROVACAO')

## Critérios de aceite

- Impedir seleção de horário de coleta já expirado no dia corrente.
- Solicitação fora de janela deve exigir justificativa antes de permitir confirmação.
- Exibir claramente quando a coleta depende de aprovação do laboratório (não confirmada de imediato).
- Funcionar em desktop, tablet e celular.

---

# Tela de Ficha do Paciente · Evolução (Portal Conecta)

## Objetivo

Mostrar o histórico de exames de um paciente e a evolução de parâmetros-chave ao longo do tempo, para apoiar a avaliação clínica do veterinário.

## Campos

Somente dados de leitura:

- Dados cadastrais do paciente (nome, espécie, raça, sexo, idade, tutor).
- Quick stats: exames realizados, último atendimento, próximo recall, alertas ativos.
- Gráfico de evolução de um parâmetro selecionável, com faixa de referência.
- Linha do tempo de exames realizados (data, tipo de exame, veterinário responsável).

## Ações

- Selecionar qual parâmetro visualizar no gráfico.
- Abrir um laudo específico a partir da linha do tempo.
- Solicitar novo exame para este paciente (atalho).

## Estados

- Carregando.
- Paciente sem histórico (estado vazio, apenas dados cadastrais).
- Parâmetro selecionado sem dados suficientes para gráfico (menos de 2 pontos).
- Alerta ativo no paciente (destaque visual).
- Falha ao carregar.

## Permissões

- Visível apenas para usuários da clínica associada ao paciente (ou veterinário que o atendeu, no caso de autônomos).
- Exige `PATIENT_VIEW`.

## Integração esperada

GET /api/v1/portal/patients/{id}
GET /api/v1/portal/patients/{id}/timeline?parameter_key=
GET /api/v1/portal/patients/{id}/alerts

Response (timeline):
- points: [{ date, value, reference_min, reference_max }]

## Critérios de aceite

- Gráfico deve exibir a banda de referência do parâmetro junto aos pontos do paciente.
- Linha do tempo ordenada do mais recente para o mais antigo.
- Não expor dados de pacientes de outras clínicas sob nenhuma circunstância.
- Funcionar em desktop, tablet e celular.

---

# Tela de Laudo + Interpretação por IA (Portal Conecta)

## Objetivo

Permitir que o veterinário visualize o laudo finalizado e converse com um assistente de IA para apoiar a interpretação clínica dos resultados.

## Campos

- Nenhum campo de edição do laudo (somente leitura neste portal).
- Campo de mensagem do chat com a IA:
  - obrigatório para envio;
  - texto livre.

## Ações

- Visualizar PDF do laudo.
- Baixar PDF do laudo.
- Enviar pergunta à IA.
- Aceitar sugestão da IA de exames complementares (abre solicitação pré-preenchida).
- Consultar histórico de conversas anteriores sobre este laudo.

## Estados

- Carregando laudo.
- Laudo disponível.
- Laudo ainda não assinado (bloqueia acesso, mostra "em análise").
- Enviando pergunta à IA.
- Resposta da IA em streaming.
- Falha na resposta da IA.
- Limite diário de interações atingido.

## Permissões

- Exige `LAUDO_VIEW` no escopo do próprio paciente/clínica.
- Uso do chat IA exige que o laudo já esteja assinado.

## Integração esperada

GET /api/v1/portal/laudos/{id}
GET /api/v1/portal/laudos/{id}/pdf-url

POST /api/v1/portal/laudos/{id}/ai-chat
Request: { message }
Response: streaming de { reply_chunk } e, ao final, { suggested_actions: [{ kind, exam_ids }] }

GET /api/v1/portal/laudos/{id}/ai-history

## Critérios de aceite

- Toda resposta da IA deve exibir o aviso de que não substitui avaliação clínica presencial.
- Interações da IA devem ficar salvas e recuperáveis ao reabrir o laudo.
- Sugestão de exame complementar deve redirecionar para o fluxo de Solicitar Exame com os itens já marcados.
- Funcionar em desktop, tablet e celular.

---

# Telas do Aplicativo Mobile (Portal Conecta · Painel, Pedido, Chat IA)

## Objetivo

Reproduzir em formato app as três jornadas mais frequentes do veterinário fora do computador: acompanhar exames, abrir um pedido e consultar a IA sobre um laudo.

## Campos

- Painel: somente leitura (mesmos dados da tela de Painel da Clínica web).
- Pedido: mesmos campos da tela de Solicitar Exame web, apresentados em passos (wizard).
- Chat IA: mesmo campo de mensagem da tela de Laudo + IA web.

## Ações

- Painel: puxar para atualizar; tocar em item recente; abrir novo pedido (botão de ação central).
- Pedido: avançar/voltar entre passos; confirmar solicitação.
- Chat IA: enviar mensagem; ver sugestão de exame complementar.

## Estados

- Mesmos estados das versões web equivalentes.
- Adicional: sem conexão (modo offline, exibindo últimos dados/PDFs já baixados).
- Notificação push recebida (laudo pronto, fechamento disponível, coleta aprovada).

## Permissões

Idênticas às telas web equivalentes.

## Integração esperada

Mesmos endpoints das telas web equivalentes, mais:

POST /api/v1/portal/push-token
Request: { token, platform }

## Critérios de aceite

- Login com biometria quando disponível no aparelho.
- Notificações push devem levar diretamente à tela do item referido (laudo, protocolo ou fechamento).
- Últimos PDFs abertos devem permanecer acessíveis sem conexão.
- Funcionar em iOS e Android nas resoluções correntes de mercado.
