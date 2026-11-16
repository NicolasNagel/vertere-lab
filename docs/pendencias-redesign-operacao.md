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
- [ ] Axe/e2e não cobre a tela de novo protocolo; rodar verificação de acessibilidade nela.
- [ ] Seta do dropdown de campo aparece "quebrada" quando aberto na captura imediata
      (provável transição de 120 ms; confirmar com espera).

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
