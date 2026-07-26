# ADR-004 — Proprietário embutido em `Patient`, sem módulo `Owner` nem tela própria

- **Status**: aceita
- **Data**: 2026-07-25
- **Decisores**: Nicolas Nagel (PO/dev), Claude (execução)

## Contexto

Fase 2 do roadmap (`docs/05-roadmap-backlog.md` §4), itens 4 (proprietários) e 5 (pacientes) —
próximo depois de clínicas, veterinários e vínculo veterinário-clínica. O modelo de domínio
(`docs/03-modelo-de-dominio.md` §1/§2, contexto Master Data) lista `Owner` e `Patient` como
entidades separadas, com o grafo de dependência mostrando `CLINIC --> OWNER --> PATIENT`. O
catálogo de permissões (`docs/07-nucleo-v1.md` §2.2) reserva pares distintos —
`owners.read`/`owners.manage` e `patients.read`/`patients.manage` — e §3.2/§3.5 descreve
"criação rápida" de proprietário e paciente como cadastros com **endpoints próprios**, sugerindo
`Owner` como agregado independente.

Uma primeira tentativa nesta sessão seguiu essa leitura literalmente: um módulo
`backend/app/modules/owners/` completo (domain/application/infrastructure/api, CRUD,
inativação) foi iniciado. O usuário interrompeu explicitamente: **não existe tela de cadastro de
Proprietários** — a única tela desta fatia é a de **Pacientes**, e "Owner é só mais uma
informação do paciente". Sem essa correção, o sistema teria ganhado um agregado, um repositório,
uma migration e uma API inteira para uma entidade que nenhuma tela ou caso de uso desta fase usa
de forma independente — exatamente o tipo de complexidade prematura que `CLAUDE.md`
("Princípios de código", YAGNI) e `product-domain.md` ("Novo cadastro subsequente... exige
política de duplicidade própria antes de existir") pedem para evitar até que o requisito seja
real.

Se nada fosse decidido, a implementação ficaria ambígua entre seguir `docs/03`/`docs/07` à risca
(criar `Owner` como agregado com FK a partir de `Patient`) ou embutir os dados do tutor
diretamente em `Patient` sem registrar por quê — desviando de dois documentos de referência
silenciosamente.

## Decisão

**Dados do proprietário (`owner_name`, `owner_phone`, `owner_document`) são colunas simples em
`patients`** (`backend/app/modules/patients/infrastructure/models.py`), não uma entidade `Owner`
separada com tabela, repositório ou API própria. `owner_name` é obrigatório; `owner_phone` e
`owner_document` são opcionais, sem validação de dígito verificador.

Não há módulo `backend/app/modules/owners/` nem endpoint `/owners`. A tela de Pacientes
(`frontend/src/features/patients/`) captura o tutor como campos de texto diretos no mesmo
formulário — não há busca/seleção de proprietário existente, nem ação "criar novo proprietário"
separada da criação do paciente.

Nenhuma verificação de duplicidade é aplicada a `owner_name` nem a `patients.name`: o mesmo nome
de tutor (ou de paciente) pode se repetir livremente entre registros — decisão confirmada pelo
usuário ("Só o nome do proprietário está ótimo, o foco maior das informações é o do paciente"),
tratando duplicidade como não-prioridade nesta fatia, ao contrário do CRMV único de
`Veterinarian` (ADR-003).

`Species` também não ganhou tela própria: é uma tabela seedada com valores fixos (Cão, Gato, Ave,
Outro — `backend/alembic/versions/0007_create_species.py`), consumida como select no formulário
de Paciente, gated pela permissão `patients.read` já existente (sem código de permissão próprio).
`breed` (raça) é texto livre opcional em `patients`, sem tabela `Breed`.

## Alternativas consideradas

- **Módulo `Owner` completo com CRUD e endpoints próprios, sem tela dedicada** — a implementação
  inicial desta sessão antes da correção do usuário. Rejeitada: gera um agregado inteiro (domain,
  application, infra, API, migration, testes) sem nenhum consumidor real além do próprio
  formulário de Paciente, que passaria a fazer uma segunda chamada de API (buscar/criar Owner)
  antes de criar o Paciente — complexidade que nenhuma tela ou caso de uso desta fase pede.
- **`Owner` com tela própria de cadastro (mestre-detalhe como Clínicas/Veterinários)** —
  rejeitada explicitamente pelo usuário: não existe mockup nem necessidade de gerenciar
  proprietários independentemente de um paciente.
- **Deduplicação de `Owner` por nome + telefone normalizados** (opção originalmente cogitada) —
  rejeitada em favor de nenhuma deduplicação: o usuário priorizou simplicidade, já que o dado
  central da tela é o paciente, não o tutor.
- **`Species`/`Breed` como módulo CRUD completo com tela própria** — rejeitada por YAGNI: sem
  mockup nem necessidade de editar a lista de espécies pela UI nesta fase; `Species` seedada
  resolve o campo obrigatório do formulário de Paciente sem essa superfície extra.

## Consequências

- `docs/03-modelo-de-dominio.md` fica **desatualizado nesta fatia especificamente** — `Owner`
  segue listado como entidade do contexto Master Data, mas não existe como tabela/módulo. Mesma
  situação já registrada para `ClinicContact` em ADR-002: aceitável enquanto documentado aqui.
- As permissões `owners.read`/`owners.manage` (seedadas em `0002_seed_identity_catalog.py` e já
  concedidas a `RECEPTION`) ficam **sem uso** — nenhum endpoint as exige. Não foram removidas do
  catálogo porque removê-las quebraria a numeração/seed já aplicada; ficam como uma pendência
  documentada, não como uma inconsistência silenciosa.
- Se um requisito real de proprietário independente do paciente surgir (ex.: portal do tutor,
  histórico de todos os pacientes de um mesmo tutor, deduplicação por CPF), a migração é aditiva:
  criar `owners`, popular a partir dos valores hoje distintos em `patients.owner_name` (com
  merge manual dos casos variantes, já que hoje não há normalização), adicionar `owner_id` a
  `patients` mantendo as colunas atuais até a migração de dado ser validada — sem quebrar
  atendimentos ou fechamentos já existentes, já que nada além de `patients` referencia esses
  campos.
- Nome de paciente ou de tutor duplicado nunca é bloqueado nem avisado nesta fatia — se isso virar
  um problema operacional real (ex.: erro de digitação criando registros duplicados sem
  detecção), a política de duplicidade precisa ser decidida e registrada antes de qualquer atalho
  ad-hoc, seguindo `product-domain.md`.

## Verificação

Suíte automatizada verde antes da entrega (commit `1a9211e`): backend (`ruff check` + `ruff format
--check` + mypy estrito em `domain`/`application` + pytest — 118 testes, incluindo integração com
Postgres real via Testcontainers cobrindo criação, edição com conflito de `row_version`,
inativação preservando histórico, e busca por nome de tutor); frontend (`tsc -b` + oxlint +
vitest — 51 testes, `vite build` de produção ok).

**Verificação manual em 2026-07-26**, Postgres local, backend e frontend rodando, logado como
usuário real, testado no Chrome:
- Criar paciente (`Rex`, espécie Cão, raça SRD, idade "2 anos") com tutor embutido (`Maria Souza`,
  telefone, documento) → `201 Created`, painel de detalhe mostra os dois grupos de campos
  ("Dados gerais" e "Tutor") corretos.
- Editar nome do paciente → `200 OK`, atualização refletida na lista e no detalhe.
- Buscar por nome do tutor (`"maria"`) → encontra o paciente correto (confirma que a busca cobre
  `owner_name`, não só `patients.name`).
- Inativar via menu "Mais ações" → `200 OK`, badge muda para "Inativo", registro preservado (não
  removido), ação de editar continua disponível, kebab menu de inativar some.
- `POST /patients` com `species_id` inexistente → `404 NOT_FOUND` ("Espécie não encontrada."), não
  mais um `500` — confirma a correção feita depois desta ADR
  (`app/modules/patients/application/create_patient.py`, ver commit de correções pós-fatia de
  Exames) que passou a validar `species_id` antes de persistir, o mesmo padrão já usado em
  `CreateExamUseCase` para `category_id`/`species_ids`.

Nenhum bug novo encontrado nesta verificação — dado de teste removido ao final.
