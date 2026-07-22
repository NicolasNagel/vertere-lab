# Modelo de Domínio — Vertere Lab V2

## 1. Contextos delimitados

### Identity & Access

- `User`;
- `Credential` ou identidade externa;
- `Role`;
- `Permission`;
- `RolePermission`;
- `LabMembership`;
- `ClinicMembership`;
- `Session`;
- `AccessAudit`.

### Master Data

- `Clinic`;
- `ClinicContact`;
- `Veterinarian`;
- `VeterinarianClinic`;
- `Owner`;
- `Patient`;
- `Species`;
- `Breed`;
- `Exam`;
- `ExamPanel`;
- `ExamPanelItem`;
- `PriceTable`;
- `PriceTableItem`;
- `CollectionMethod`;
- `ServiceType`.

### Attendance

- `AttendanceRecord` — raiz do agregado operacional;
- `AttendanceExam` — item de exame;
- `AttendanceCollection` — dados da coleta;
- `AttendancePricing` — resumo financeiro;
- `AttendanceSequence` — sequência anual;
- `AttendanceRevision` — revisão auditável quando necessária.

### Billing

- `MonthlyClosure`;
- `MonthlyClosureItem`;
- `FinancialAdjustment`;
- `ClosureReopening`;
- `BillingExport`.

### Audit & Integration

- `AuditLog`;
- `OutboxEvent`;
- `IdempotencyRecord`;
- `ImportBatch`;
- `ImportRow`;
- `StoredFile`.

## 2. Grafo de dependência do núcleo

```mermaid
flowchart LR
    USER[Usuário e permissões] --> CLINIC[Clínica]
    CLINIC --> VET[Veterinário e vínculo]
    CLINIC --> OWNER[Proprietário]
    OWNER --> PATIENT[Paciente]
    CATALOG[Exames e preços] --> ATT[Registro de Atendimento]
    VET --> ATT
    PATIENT --> ATT
    CLINIC --> ATT
    ATT --> CLOSE[Fechamento Mensal]
    ATT --> RESULTS[Resultados futuros]
    ATT --> REPORTS[Laudos futuros]
    ATT --> PORTAL[Portal futuro]
```

## 3. Agregado `AttendanceRecord`

### Responsabilidade

Representar o fato operacional e financeiro de que uma clínica solicitou um ou mais exames para um paciente, sob responsabilidade de um veterinário, em uma data e condição de atendimento específicas.

### Campos essenciais

- `id` opaco;
- `protocol_year`;
- `protocol_sequence`;
- `protocol_number` de negócio;
- `clinic_id`;
- `veterinarian_id`;
- `owner_id`;
- `patient_id`;
- `service_date`;
- `requested_at`;
- `status`;
- `service_type_id`;
- `collection_method_id`;
- `notes` sanitizadas;
- `subtotal`;
- `discount_total`;
- `surcharge_total`;
- `grand_total`;
- `currency`;
- `billing_competence`;
- `monthly_closure_id` opcional;
- `created_by`;
- `updated_by`;
- `created_at`;
- `updated_at`;
- `row_version` para concorrência otimista.

### Itens `AttendanceExam`

Cada item preserva:

- `exam_id`;
- código e nome no momento do registro;
- versão do exame;
- tabela de preço e item de origem;
- preço-base;
- desconto;
- adicional;
- total final;
- quantidade;
- justificativa de override;
- usuário que autorizou override;
- situação financeira;
- referência ao fechamento quando consolidado.

### Estados iniciais

`DRAFT -> CONFIRMED -> IN_PROGRESS -> COMPLETED`

Estados alternativos:

- `CANCELLED`;
- `ON_HOLD`.

Regras:

- somente `DRAFT` pode ser apagado fisicamente e apenas se não possuir dependência;
- confirmação gera protocolo;
- cancelamento exige motivo;
- atendimento incluído em fechamento não pode sofrer alteração financeira direta;
- edição de dados cadastrais que afete documento histórico deve preservar snapshot ou revisão.

## 4. Cadastros subsequentes

O formulário de atendimento pode oferecer criação rápida, mas cada cadastro é um caso de uso independente.

### Regras

- nenhuma entidade é criada por simples ausência em uma busca;
- toda criação rápida exige confirmação do usuário;
- backend executa busca de duplicidade provável antes de criar;
- cada entidade possui permissão própria;
- falha ao criar cadastro não pode deixar atendimento parcialmente confirmado;
- rascunho pode referenciar IDs já persistidos, nunca objetos temporários sem identidade;
- vínculos devem ser validados no momento da confirmação;
- inativação não remove histórico.

### Ordem de resolução

1. clínica;
2. veterinário e vínculo com clínica;
3. proprietário;
4. paciente;
5. catálogo e preço;
6. atendimento;
7. fechamento.

## 5. Identidade e permissão

### Modelo

Permissão = `resource.action`, por exemplo:

- `users.read`;
- `users.create`;
- `users.update`;
- `roles.assign`;
- `clinics.manage`;
- `veterinarians.manage`;
- `owners.manage`;
- `patients.manage`;
- `attendances.read`;
- `attendances.create`;
- `attendances.update`;
- `attendances.cancel`;
- `attendances.override_price`;
- `closures.preview`;
- `closures.close`;
- `closures.reopen`;
- `closures.adjust`;
- `audit.read`.

Toda autorização considera:

- usuário ativo;
- sessão válida;
- permissão;
- escopo de laboratório ou clínica;
- estado da entidade;
- eventual regra de propriedade.

Papéis são agrupadores de permissões, não regras hard-coded no domínio.

## 6. Fechamento mensal

### `MonthlyClosure`

Campos essenciais:

- `id`;
- `clinic_id`;
- `competence_year`;
- `competence_month`;
- `period_start`;
- `period_end`;
- `status`;
- `item_count`;
- `subtotal`;
- `discount_total`;
- `surcharge_total`;
- `grand_total`;
- `generated_by`;
- `closed_by`;
- `generated_at`;
- `closed_at`;
- `reopened_at` opcional;
- `version`;
- `integrity_hash` opcional.

### Estados

`DRAFT -> CLOSED`

Alternativos:

- `CANCELLED` antes de fechar;
- `REOPENED` somente por fluxo excepcional;
- após correção, nova versão `CLOSED`.

### Elegibilidade

Um item é elegível quando:

- pertence à clínica;
- está dentro da competência definida;
- atendimento não está cancelado;
- item não está cancelado;
- não pertence a outro fechamento ativo;
- possui valor final válido;
- possui todos os campos financeiros obrigatórios.

### Invariantes

- unicidade ativa por clínica e competência;
- fechamento fechado é imutável;
- itens do fechamento são snapshots;
- soma dos itens deve ser igual ao cabeçalho;
- cada item fonte é associado a no máximo um fechamento ativo;
- reabertura exige permissão, justificativa e auditoria;
- ajustes não alteram o valor original do atendimento;
- registro retroativo em período fechado segue política de ajuste ou reabertura, nunca inserção silenciosa.

## 7. Restrições de banco obrigatórias

- `UNIQUE(protocol_year, protocol_sequence)`;
- `UNIQUE(clinic_id, competence_year, competence_month)` para fechamento ativo, implementada conforme estratégia de status;
- `CHECK(grand_total >= 0)`;
- `CHECK(discount_total >= 0)`;
- `CHECK(surcharge_total >= 0)`;
- FKs para todos os cadastros;
- `NUMERIC(14,2)` para dinheiro;
- `TIMESTAMPTZ` para timestamps;
- `DATE` ou ano/mês explícito para competência;
- índices por clínica, data, status, protocolo, paciente e veterinário;
- versão de linha em edições concorrentes.

## 8. Auditoria

Ações mínimas:

- login e falha relevante;
- criação, ativação e inativação de usuário;
- alteração de papel e permissão;
- criação e atualização de cadastro mestre;
- confirmação, edição crítica e cancelamento de atendimento;
- override de preço;
- geração, fechamento, ajuste e reabertura mensal;
- importação e reconciliação.

O log registra ator, escopo, ação, entidade, estado anterior reduzido, estado posterior reduzido, motivo, IP quando aplicável, request ID e timestamp. Não registra senha, token ou conteúdo sensível desnecessário.
