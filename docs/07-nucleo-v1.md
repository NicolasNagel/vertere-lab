# Especificação do Núcleo da V1

## 1. Objetivo

Definir com precisão os três pilares que devem ser concluídos antes dos módulos de laudos, portal, coleta e comunicação:

1. usuários e permissões;
2. Registro de Atendimento e cadastros subsequentes;
3. fechamento mensal.

## 2. Usuários e permissões

### 2.1 Papéis iniciais sugeridos

| Papel | Escopo | Finalidade |
|---|---|---|
| `SUPER_ADMIN` | global | manutenção excepcional da plataforma |
| `LAB_ADMIN` | laboratório | usuários, permissões e configurações |
| `RECEPTION` | laboratório | cadastros e atendimentos |
| `FINANCE` | laboratório | preços, prévias, fechamentos e ajustes |
| `TECHNICAL` | laboratório | operação técnica futura |
| `TECHNICAL_MANAGER` | laboratório | revisão e laudos futuros |
| `CLINIC_ADMIN` | clínica | usuários e visão da própria clínica |
| `VETERINARIAN` | clínica | solicitações e laudos próprios/permitidos |
| `CLINIC_STAFF` | clínica | consulta limitada |

A aplicação verifica permissões, não nomes de papéis.

### 2.2 Permissões mínimas

```text
users.read
users.create
users.update
users.deactivate
roles.read
roles.assign
permissions.read
clinics.read
clinics.manage
veterinarians.read
veterinarians.manage
owners.read
owners.manage
patients.read
patients.manage
catalog.read
catalog.manage
pricing.read
pricing.manage
attendances.read
attendances.create
attendances.update
attendances.cancel
attendances.override_price
closures.read
closures.preview
closures.close
closures.adjust
closures.reopen
audit.read
imports.execute
```

### 2.3 Regras

- deny by default;
- usuário inativo não autentica nem renova sessão;
- permissão é avaliada no backend;
- acesso de clínica exige membership ativo;
- usuário de clínica nunca escolhe `clinic_id` fora das memberships;
- usuário interno com escopo global precisa de permissão explícita;
- alteração de papel é auditada;
- papel e memberships são alterados atomicamente com `expected_row_version`;
- mudança de acesso revoga todas as sessões do usuário afetado;
- privilégios críticos podem exigir reautenticação;
- nenhum endpoint sensível depende apenas de ocultar botão.

Contrato de acesso:

```text
PATCH /api/v1/users/{id}/access { role_id, clinic_ids, expected_row_version }
PATCH /api/v1/users/{id}/role   # compatibilidade, depreciado
```

Login e leituras de usuário expõem `role_scope`, `clinic_ids` e `row_version`. Papéis `CLINIC`
exigem ao menos uma membership ativa; papéis `LAB`/`GLOBAL` exigem membership de laboratório
ativa.

Cadastros estruturantes usam o mesmo contexto: atores `CLINIC` só listam suas clínicas e os
veterinários/pacientes associados a elas. `Patient` expõe e recebe `clinic_id`; linhas anteriores
à migration `0038` podem permanecer `NULL`, ficam restritas a `LAB/GLOBAL` e só recebem clínica
por atualização auditada. A confirmação de atendimento rejeita paciente de clínica diferente.

## 3. Registro de Atendimento

### 3.1 Tela principal

Seções recomendadas:

1. identificação do atendimento;
2. clínica e veterinário;
3. proprietário e paciente;
4. exames;
5. coleta e atendimento;
6. valores;
7. observações;
8. resumo e confirmação.

Na V1, coleta e tipo de atendimento são valores controlados no próprio agregado:
`collection_method` normaliza os cinco valores encontrados na planilha e `service_level`
distingue atendimento normal de plantão. Plantão aplica no servidor o adicional configurado
no exame; o frontend nunca envia o valor do adicional.

### 3.2 Criação rápida

Cada seletor de cadastro oferece:

- busca normalizada;
- resultados prováveis;
- aviso de possível duplicidade;
- botão de criação somente com permissão;
- modal ou drawer sem perder o rascunho;
- retorno do novo ID após sucesso;
- tratamento de conflito se outro usuário criou o mesmo registro.

### 3.3 Confirmação atômica

A confirmação deve:

1. revalidar todos os IDs;
2. verificar status e vínculo;
3. resolver preço vigente no servidor;
4. validar overrides;
5. calcular totais;
6. obter próximo protocolo;
7. persistir cabeçalho e itens;
8. persistir auditoria e outbox;
9. commit;
10. retornar representação completa.

Nenhum atendimento confirmado pode existir sem ao menos um item.

### 3.4 Regras de edição

- rascunho: edição ampla conforme permissão;
- confirmado e ainda aberto financeiramente: edição controlada;
- campos críticos exigem auditoria;
- mudança de preço exige `attendances.override_price` e motivo;
- cancelamento exige motivo;
- fechado: sem alteração financeira direta;
- conflito de versão retorna HTTP 409;
- alteração não deve apagar o valor anterior do audit log.

### 3.5 Endpoints iniciais

```text
POST   /api/v1/attendances/drafts
GET    /api/v1/attendances
GET    /api/v1/attendances/{id}
PATCH  /api/v1/attendances/{id}
POST   /api/v1/attendances/{id}/confirm
POST   /api/v1/attendances/{id}/cancel
GET    /api/v1/attendances/{id}/timeline
```

Cadastros possuem endpoints próprios. Não criar proprietário/paciente implicitamente dentro de `/confirm`.

## 4. Fechamento por período

### 4.1 Conceito de período

O fechamento aceita qualquer intervalo civil inclusivo (`period_start`/`period_end`) e seleciona
atendimentos por `service_date`. `billing_competence` continua gravada na confirmação para
rastreabilidade financeira, mas não decide a elegibilidade do fechamento. Mudanças retroativas
seguem política formal.

### 4.2 Prévia

A prévia exibe:

- clínica;
- período;
- quantidade de atendimentos;
- quantidade de itens;
- subtotal;
- descontos;
- adicionais;
- total;
- atendimentos cancelados;
- itens bloqueados;
- motivos de inconsistência;
- diferença em relação a uma prévia anterior.

A prévia não bloqueia itens e não é documento final.

### 4.3 Fechar

Pré-condições:

- permissão `closures.close`;
- clínica ativa ou elegível;
- período válido (`period_end >= period_start`);
- nenhuma inconsistência bloqueante;
- nenhuma outra closure `CLOSED` sobreposta para a mesma clínica;
- idempotency key;
- justificativa quando a política exigir.

Pós-condições:

- fechamento `CLOSED`;
- snapshots persistidos;
- itens associados;
- totais reconciliados;
- auditoria;
- evento de outbox;
- itens financeiros protegidos.

### 4.4 Ajuste

Um ajuste:

- referencia o fechamento e, quando possível, o item original;
- possui tipo crédito ou débito;
- possui valor, motivo, autor e data;
- não modifica snapshot original;
- aparece em exportações e versões posteriores.

### 4.5 Reabertura

Reabertura é excepcional:

- permissão específica;
- reautenticação quando adotada;
- justificativa obrigatória;
- auditoria;
- bloqueio concorrente;
- preservação da versão anterior;
- nova versão ao fechar novamente.

### 4.6 Endpoints iniciais

```text
GET  /api/v1/closures/preview?clinic_id=&period_start=&period_end=
POST /api/v1/closures                 { clinic_id, period_start, period_end }
GET  /api/v1/closures
GET  /api/v1/closures/{id}
GET  /api/v1/closures/by-period?clinic_id=&period_start=&period_end=
POST /api/v1/closures/{id}/adjustments
POST /api/v1/closures/{id}/reopen
GET  /api/v1/closures/{id}/export
```

Período de fechamento é livre (`period_start`/`period_end`), não só mês calendário — algumas
clínicas fecham quinzenalmente. Elegibilidade decide por `service_date` do atendimento dentro do
período (`.claude/rules/13-monthly-closure.md`).

## 5. Critérios de aceite do núcleo

- nenhuma permissão é decidida somente no frontend;
- clínica A não lê nem altera dados da B;
- protocolo é único sob concorrência;
- atendimento duplicado por retry não ocorre;
- preços históricos permanecem estáveis;
- fechamento duplica zero itens;
- total do fechamento é exato;
- atendimento fechado rejeita alteração financeira;
- ajuste e reabertura são rastreáveis;
- migração reconcilia contagem e valores;
- todos os fluxos críticos têm testes E2E.
