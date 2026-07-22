# Roadmap e Backlog — Vertere Lab V2

## 1. Regra de priorização

Nenhum módulo dependente de atendimento deve avançar com dados falsos, tabelas provisórias ou atalhos que violem o modelo definitivo. O projeto será entregue por fatias verticais.

## 2. Fase 0 — Descoberta e decisões

Entregáveis:

- glossário aprovado;
- campos obrigatórios do Registro de Atendimento;
- matriz de permissão;
- política de duplicidade;
- política de alteração e cancelamento;
- regra de competência financeira;
- regra de atraso e retroatividade;
- política de reabertura;
- catálogo inicial de exames;
- aliases da planilha;
- ADRs de autenticação, protocolo, tenant e fechamento.

Gate:

- PO e operação conseguem executar em protótipo o cadastro de um atendimento e a conferência de um fechamento.

## 3. Fase 1 — Fundação técnica e identidade

Épicos:

- estrutura backend/frontend;
- configuração por ambiente;
- FastAPI, SQLAlchemy, Alembic e PostgreSQL;
- React e design system mínimo;
- autenticação;
- usuários;
- papéis e permissões;
- memberships por clínica;
- auditoria;
- tratamento de erros;
- CI/CD;
- observabilidade básica.

Gate:

- usuário ativo entra;
- usuário inativo não entra;
- alteração de papel é auditada;
- clínica A não acessa clínica B;
- permissões são testadas no backend.

## 4. Fase 2 — Cadastros estruturantes

Ordem:

1. clínicas e contatos;
2. veterinários;
3. vínculo veterinário-clínica;
4. proprietários;
5. pacientes;
6. espécies e raças;
7. catálogo de exames e painéis;
8. tabelas de preço e vigência;
9. métodos de coleta e tipos de atendimento.

Para cada cadastro:

- criar;
- editar;
- inativar;
- consultar;
- buscar;
- detectar duplicidade provável;
- auditar;
- testar permissão;
- preservar histórico.

Gate:

- dados necessários a um atendimento completo existem e não dependem de texto livre indevido.

## 5. Fase 3 — Registro de Atendimento

### Incremento 3.1 — Rascunho

- formulário principal;
- seleção de clínica;
- seleção de veterinário;
- seleção/criação rápida de proprietário e paciente;
- seleção de exames;
- persistência de rascunho;
- validação progressiva.

### Incremento 3.2 — Confirmação

- validação completa;
- idempotency key;
- sequência transacional;
- snapshots de exame e preço;
- cálculo server-side;
- auditoria;
- timeline.

### Incremento 3.3 — Manutenção

- busca e filtros;
- edição com versão;
- cancelamento com motivo;
- override de preço;
- bloqueio por estado;
- exportação simples de conferência.

Gate:

- fluxos concorrentes não duplicam protocolo;
- duplo clique não duplica atendimento;
- atualização de preço não altera atendimento existente;
- permissão e tenant estão cobertos;
- valores reconciliam com casos de teste.

## 6. Fase 4 — Fechamento mensal

### Incremento 4.1 — Prévia

- filtro por clínica e competência;
- itens elegíveis;
- itens bloqueados e motivos;
- contagens;
- subtotal, descontos, adicionais e total;
- drill-down para atendimento.

### Incremento 4.2 — Fechamento

- lock por clínica e competência;
- idempotência;
- snapshot;
- associação dos itens;
- imutabilidade;
- auditoria;
- exportação CSV/PDF simples, fora da transação.

### Incremento 4.3 — Exceções

- ajuste posterior;
- reabertura excepcional;
- atendimento retroativo;
- cancelamento posterior;
- histórico de versões.

Gate:

- mesma competência não fecha duas vezes;
- totais do cabeçalho e itens são idênticos;
- atendimento fechado não é alterado diretamente;
- reabertura e ajuste são auditados;
- fechamento é reproduzível.

## 7. Fase 5 — Migração e piloto

- staging da planilha;
- normalização;
- aliases;
- dry-run;
- relatório de exceções;
- importação idempotente;
- reconciliação dos 1.794 registros válidos e do valor validado;
- piloto com usuários internos;
- operação paralela curta;
- corte da planilha.

## 8. Fase 6 — Resultados e laudos

- resultados estruturados;
- revisão técnica;
- laudo versionado;
- PDF;
- storage privado;
- publicação e download auditados.

## 9. Fase 7 — Portal, coletas e comunicação

- portal das clínicas;
- histórico do paciente;
- agenda e solicitação de coleta;
- notificações;
- comunicados 1:N;
- respostas e anexos.

## 10. Definition of Ready

Uma história está pronta quando informa:

- problema e resultado;
- ator;
- permissão;
- escopo;
- dados obrigatórios;
- duplicidade;
- estado anterior e posterior;
- regra financeira;
- impacto no atendimento;
- impacto no fechamento;
- auditoria;
- erros;
- critérios de aceite;
- testes;
- estratégia de migração quando aplicável.

## 11. Definition of Done

- implementação completa;
- Ruff passa;
- mypy passa no escopo definido;
- TypeScript passa;
- testes unitários e de integração passam;
- E2E crítico passa;
- migration revisada e aplicada em ambiente de teste;
- autorização backend testada;
- auditoria verificada;
- logs e métricas adequados;
- documentação atualizada;
- nenhum segredo ou PII indevida;
- rollback considerado;
- critérios de aceite demonstrados.

## 12. Ordem proibida

Não iniciar como prioridade antes do gate do fechamento:

- IA;
- WhatsApp;
- aplicativo móvel;
- dashboards sofisticados;
- microserviços;
- BI avançado;
- integração com equipamentos;
- automações que dependam de atendimento ainda instável.
