---
# Regras do Registro de Atendimento — o agregado central. Carrega ao tocar esse módulo.
paths:
  - "backend/app/modules/attendances/**"
  - "frontend/src/features/attendances/**"
---
# Regras Específicas do Registro de Atendimento

## Centralidade
`AttendanceRecord` é o agregado central do sistema. Resultado, laudo, portal, comunicação e
financeiro **referenciam** esse agregado — nenhum deles duplica ou recalcula seu dado.

## Criação
- Pode iniciar em `DRAFT` (rascunho).
- Confirmação exige clínica válida, veterinário vinculado, proprietário, paciente e **ao menos
  um item de exame**. Nenhum atendimento confirmado existe sem item.
- Criação rápida de cadastro subsequente (proprietário/paciente novo) é um caso de uso separado
  — nunca um efeito colateral escondido dentro do `/confirm`.
- Todo ID é **revalidado no momento da confirmação**, mesmo que já tenha sido validado ao
  selecionar (outro usuário pode ter inativado o registro nesse meio-tempo).
- Preço resolvido no backend, nunca aceito do frontend.
- Snapshot financeiro persistido junto do item, na mesma transação.
- Protocolo é transacional (ver `04-database.md`); `Idempotency-Key` obrigatória; auditoria e
  outbox no mesmo commit da confirmação.

## Cadastro subsequente (durante o atendimento)
- Nunca crie uma entidade só porque a busca voltou vazia — sempre exige confirmação explícita do
  usuário.
- Mostre duplicidade provável antes de deixar criar.
- Cada cadastro subsequente tem permissão própria (não herda a permissão de criar atendimento).
- Conflito de criação concorrente (dois usuários criando "o mesmo" proprietário ao mesmo tempo)
  retorna a entidade já existente ou `409`, conforme a política definida — nunca cria duplicata
  silenciosa.
- Cadastro inativo não pode ser usado em atendimento novo; histórico permanece intacto mesmo
  assim.

## Dinheiro
Base, desconto, adicional e total **por item**; total do cabeçalho é a soma exata dos itens.
Override de preço exige permissão (`attendances.override_price`) **e** motivo obrigatório.
Atualização da tabela de preço vigente nunca altera um snapshot já persistido. Moeda e
arredondamento centralizados em um único ponto do domínio.

## Edição
- `DRAFT`: edição ampla, conforme permissão.
- `CONFIRMED` (ainda financeiramente aberto): edição controlada.
- Toda edição usa row version; campo crítico gera diff explícito no audit log.
- Cancelamento exige motivo.
- Tudo é corrigível (cabeçalho e exames, em `CONFIRMED` e `CANCELLED`), sempre com motivo e diff no audit log; exame removido fica `CANCELLED` no histórico, exame incluído depois usa o preço vigente na data do atendimento. Desconto exige `attendances.override_price`.
- Atendimento já em fechamento é editável, mas o snapshot do fechamento nunca muda: a diferença do `grand_total` vira `FinancialAdjustment` automático no próprio fechamento (`DEBIT` aumenta, `CREDIT` reduz o que a clínica deve). Mudar clínica ou data para fora do período reverte o valor inteiro no fechamento antigo e lança no fechamento fechado que cobrir o novo destino (ou solta o vínculo se não houver). Mesmo caso de uso, mesma auditoria — não existe atalho paralelo.

## Consultas
Sempre paginadas; filtro por protocolo, clínica, veterinário, proprietário, paciente, status e
data, com índice alinhado a esses filtros reais. Usuário de clínica é restrito ao próprio
escopo — mesmo em endpoint de "busca geral". Response contém só o campo que a tela usa.

## Endpoints (docs/07-nucleo-v1.md §3.5)
```
POST   /api/v1/attendances/drafts
GET    /api/v1/attendances
GET    /api/v1/attendances/{id}
PATCH  /api/v1/attendances/{id}
POST   /api/v1/attendances/{id}/confirm
POST   /api/v1/attendances/{id}/cancel
GET    /api/v1/attendances/{id}/timeline
```
Cadastro subsequente tem endpoint próprio — **não crie proprietário/paciente implicitamente
dentro de `/confirm`.**

## Testes obrigatórios (além dos gates gerais em 08-testing.md)
Duplicidade por retry · protocolo sob concorrência real · isolamento de tenant · permissão ·
snapshot (preço/nome não regridem) · preço sem vigência definida · desconto acima da política ·
conflito de versão · bloqueio de edição pós-fechamento · auditoria presente.
