# PRD — Plataforma Vertere Lab V2

## 1. Visão

Substituir a planilha operacional do Vertere Lab por uma plataforma transacional segura, auditável e escalável. A plataforma deverá sustentar o cadastro de atendimentos, o ciclo laboratorial, o fechamento financeiro, o envio de laudos, o portal das clínicas, o histórico dos pacientes, as coletas e a comunicação 1:N.

A V1 não será considerada estável enquanto identidade, permissões, cadastros estruturantes, Registro de Atendimento e fechamento mensal não estiverem corretos.

## 2. Princípio do produto

O Registro de Atendimento é o núcleo da operação. Ele conecta:

- clínica;
- veterinário solicitante;
- proprietário/tutor;
- paciente;
- exames solicitados;
- coleta e tipo de atendimento;
- preço, desconto, adicional e total;
- competência financeira;
- resultados e laudos futuros;
- histórico e comunicação futura.

Qualquer erro nesse registro se propaga para histórico, laudo, comunicação, indicadores e fechamento. Por isso, o produto deve privilegiar integridade e rastreabilidade acima de velocidade de implementação.

## 3. Objetivos da V1

1. retirar a planilha da função de banco de dados transacional;
2. controlar quem pode acessar e modificar cada informação;
3. padronizar clínicas, veterinários, proprietários, pacientes, exames e preços;
4. registrar atendimentos sem duplicidade e com numeração segura;
5. preservar o snapshot comercial do momento do atendimento;
6. produzir fechamento mensal por clínica sem divergência;
7. manter trilha completa de alterações e exceções;
8. permitir importação reconciliada dos dados legados;
9. preparar os dados para laudos, portal e comunicação sem retrabalho estrutural.

## 4. Escopo priorizado

### P0 — núcleo obrigatório da V1

#### Identidade e acesso

- cadastro e convite de usuários;
- ativação, inativação e recuperação de acesso;
- papéis e permissões granulares;
- escopo de laboratório e escopo por clínica;
- sessões revogáveis;
- auditoria de login, bloqueio e alteração de permissão.

#### Cadastros mestres

- clínicas;
- contatos da clínica;
- veterinários;
- vínculo N:N entre veterinários e clínicas;
- proprietários/tutores;
- pacientes;
- espécies, raças e sexos controlados;
- catálogo de exames e painéis;
- tabela de preços e vigência;
- método de coleta e tipo de atendimento.

Limites da implementação atual: tutor está embutido em `Patient`, preço vigente está diretamente
em `Exam` e alguns códigos de coleta preservam nomes históricos. O fechamento, apesar do nome
interno `MonthlyClosure`, aceita período civil livre. Esses limites não alteram os critérios de
snapshot, tenant, auditoria e imutabilidade e estão detalhados em `docs/08-divida-tecnica.md`.

#### Registro de Atendimento

- criação em rascunho;
- busca e criação rápida dos cadastros subsequentes;
- numeração transacional;
- itens de exame;
- snapshot de preço;
- desconto e adicional com permissão e justificativa;
- cálculo server-side;
- edição controlada;
- cancelamento auditado;
- timeline;
- filtros e paginação;
- idempotência;
- bloqueio financeiro após fechamento.

#### Fechamento por período

- prévia por clínica e período livre (`period_start`/`period_end`);
- reconciliação de quantidade e valores;
- fechamento transacional;
- snapshot de itens;
- exportação básica;
- imutabilidade após fechamento;
- ajuste posterior auditável;
- reabertura excepcional mediante permissão e justificativa;
- prevenção de dois fechamentos concorrentes para a mesma clínica e período.

#### Migração e governança

- staging da planilha;
- normalização e aliases;
- relatório de exceções;
- dry-run;
- importação idempotente;
- reconciliação de contagem e valores;
- auditoria.

### P1 — depois de estabilizar o núcleo

- registro e revisão de resultados;
- laudos versionados;
- geração e armazenamento de PDF;
- portal web das clínicas;
- histórico por paciente;
- solicitação e agenda de coleta;
- notificações in-app e por e-mail;
- comunicação 1:N básica.

### P2 — evolução

- WhatsApp Business;
- aplicativo móvel;
- assinatura eletrônica;
- faturamento e cobrança;
- webhooks e integrações;
- IA assistiva;
- BI avançado;
- integrações com equipamentos.

## 5. Perspectiva dos agentes

### Agente PM

- protege o núcleo da V1 contra expansão prematura;
- mede adoção, retrabalho, divergência e tempo operacional;
- mantém riscos, dependências e rollout;
- trata migração como parte do produto.

Métricas principais:

- percentual de atendimentos criados no sistema;
- taxa de cadastros duplicados;
- taxa de correção após confirmação do atendimento;
- divergência financeira por fechamento;
- tempo médio para registrar um atendimento;
- quantidade de acessos negados corretamente;
- incidência de suporte por permissão;
- percentual de linhas migradas sem intervenção manual.

### Agente PO

- especifica cada campo, regra, estado, erro e permissão;
- não aceita história sem impacto no Registro de Atendimento e no fechamento;
- define critérios para criação rápida de cadastros;
- mantém catálogo de erros e glossário;
- prioriza fluxo vertical utilizável.

### Agente Arquiteto de Software

- mantém monólito modular;
- usa PostgreSQL como fonte de verdade;
- separa domínio, aplicação, apresentação e infraestrutura;
- impede regra de negócio no frontend;
- mantém autorização no backend;
- usa outbox para efeitos posteriores;
- evita microserviços e Redis prematuros;
- prepara saída da Vercel sem reescrever domínio.

### Agente Desenvolvedor

- implementa casos de uso pequenos e transacionais;
- separa modelos ORM, entidades, DTOs e schemas de API;
- cria migrations e testes junto da funcionalidade;
- não cria cadastros relacionados silenciosamente;
- não recalcula histórico por dados atuais;
- não permite modificação de atendimento financeiramente fechado.

### Agente QA

- testa primeiro permissões, cascatas cadastrais, concorrência e fechamento;
- exige PostgreSQL real em testes de integração;
- testa isolamento entre clínicas;
- mantém cenários de regressão da planilha;
- bloqueia release em divergência financeira ou vazamento de dados.

## 6. Personas

- Administrador do laboratório;
- Recepção/cadastro;
- Financeiro;
- Analista técnico;
- Responsável técnico;
- Administrador da clínica;
- Veterinário solicitante;
- Colaborador da clínica.

## 7. Jornada crítica: Registro de Atendimento

1. usuário autenticado entra no escopo autorizado;
2. seleciona uma clínica existente;
3. seleciona veterinário vinculado ou cria/regulariza vínculo com permissão;
4. localiza proprietário e paciente por busca normalizada;
5. quando necessário, abre criação rápida sem abandonar o atendimento;
6. seleciona exames ativos;
7. backend resolve tabela e preço vigentes;
8. usuário informa coleta, tipo de atendimento e dados clínicos mínimos;
9. backend valida permissões, duplicidade provável e consistência;
10. atendimento é salvo como rascunho ou confirmado;
11. confirmação gera número transacional, snapshots financeiros e evento de auditoria;
12. alterações posteriores obedecem estado, permissão, motivo e competência financeira.

## 8. Jornada crítica: Fechamento por período

1. financeiro escolhe clínica e intervalo de datas;
2. sistema verifica se o período está aberto;
3. sistema apresenta prévia com itens elegíveis, cancelados, pendentes e inconsistentes;
4. usuário resolve bloqueios obrigatórios;
5. backend recalcula a prévia dentro da transação de fechamento;
6. backend obtém lock lógico por clínica e impede sobreposição de períodos ativos;
7. fechamento e itens-snapshot são persistidos;
8. itens de atendimento recebem referência do fechamento;
9. totais e contagens são reconciliados antes do commit;
10. fechamento fechado torna os itens financeiros imutáveis;
11. correções futuras usam ajuste ou reabertura autorizada.

## 9. Requisitos não funcionais

### Integridade

- transações nos fluxos críticos;
- constraints no banco;
- dinheiro em `NUMERIC`, nunca float;
- idempotência em criação e fechamento;
- histórico sem sobrescrita silenciosa;
- sequência de protocolo sem `MAX + 1`.

### Segurança

- deny by default;
- RBAC com escopo;
- proteção contra IDOR/BOLA;
- cookies e tokens seguros;
- rate limit;
- logs sem dados sensíveis;
- auditoria append-only para ações críticas;
- política LGPD.

### Performance

- listas paginadas;
- busca com índices e normalização;
- p95 de leituras operacionais abaixo de 500 ms no backend em carga nominal;
- p95 de mutações comuns abaixo de 800 ms;
- fechamento de uma clínica com volume esperado dentro do limite operacional definido em teste;
- sem N+1 em telas críticas.

### Disponibilidade

- backup automático;
- restore testado;
- migrations com rollback operacional;
- health checks;
- observabilidade;
- deploy reproduzível.

## 10. Fora do escopo imediato

- microserviços;
- Kubernetes;
- event sourcing completo;
- aplicativo móvel nativo;
- IA clínica;
- faturamento bancário;
- integração com equipamentos;
- chat em tempo real;
- roteirização avançada.

## 11. Critério de sucesso do núcleo

O núcleo está pronto somente quando um atendimento completo pode ser criado, localizado, auditado, incluído em uma prévia, fechado mensalmente e reconciliado sem depender da planilha e sem permitir acesso ou alteração indevida.
