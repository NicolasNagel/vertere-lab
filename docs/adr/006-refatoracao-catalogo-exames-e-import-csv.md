# ADR-006 — Refatoração da tela de Exames & Preços (lista + form dedicado) e importação de CSV

- **Status**: aceita
- **Data**: 2026-07-26
- **Decisores**: Nicolas Nagel (PO/dev), Claude (execução)

## Contexto

O catálogo de exames (ADR-005) tinha lista + painel lateral de criação/edição num único
componente (`exams-page.tsx` com `ExamList`/`ExamDetail`/`ExamForm` lado a lado). Dois mockups
novos substituíram a referência visual da tela: `assets/features/screens/6-cadastro-de-exames(1).html`
(lista) e `assets/features/screens/19-editar-criar-novo-exame.html` (criação/edição dedicada) —
o mockup antigo (`6-cadastro-de-exames.html`) foi removido do repositório.

Os dois mockups novos trazem elementos sem qualquer suporte no domínio hoje:

1. **"Parâmetros do laudo"** no form de exame — parâmetros com faixa de referência por
   espécie/faixa etária. É, na prática, o domínio de `Report`/Laudo (P1 no roadmap,
   `docs/05-roadmap-backlog.md`) e a ordem de prioridade do projeto proíbe explicitamente
   construir P1 antes do núcleo (`CLAUDE.md` §"Prioridade de implementação", "ordem proibida").
2. **"Prazo de entrega"** (turnaround time) — campo novo em `Exam`, sem menção em
   `spec-pages.md` nem em `docs/03-modelo-de-dominio.md`.
3. **Painel "Taxas de plantão"** na tela de lista — configuração global de sobretaxa de plantão
   (normal/especial), claramente um agregado diferente de `Exam` (é configuração do laboratório,
   não do catálogo por item).
4. **Botão "Importar CSV"** — este já estava especificado em `spec-pages.md:443-445`
   (`POST /api/v1/exams/import`) e tinha sido explicitamente **adiado** na ADR-005 (decisão 4:
   "funcionalidade suficientemente separada... justifica sua própria fatia futura, depois do CRUD
   básico estar estável em produção"). O CRUD básico já está em produção há uma fatia, então essa
   condição de adiamento deixou de valer.

Perguntado explicitamente (`AskUserQuestion`, não assumido), o usuário decidiu: (1)-(3) ficam de
fora desta entrega, sem nem virar placeholder estático; (4) entra de verdade, backend e frontend
completos. Essa decisão é o que motiva a maior parte das pendências registradas abaixo — este ADR
existe justamente para deixá-las rastreáveis, em vez de ficarem implícitas no código.

## Decisão

**1. Tela de criação/edição vira rota própria, não painel lateral.** Novas rotas
`/cadastros/exames/novo` e `/cadastros/exames/:examId/editar` (`ExamFormPage`), reaproveitando
quase integralmente `ExamForm` (schema Zod, mutations, lógica de categoria/espécie) — só o layout
virou grid de duas colunas com cards, e os botões Cancelar/Salvar migraram para o header da
página via atributo HTML nativo `form=` (sem duplicar lógica de submit). `ExamDetail` (visão
somente-leitura em painel lateral) foi removida — clicar na linha da tabela abre a edição direto,
mais fiel ao mockup 19 (que não mostra um modo somente-leitura separado) e mais simples (YAGNI).

**2. Lista vira tabela com sidebar de filtro + cards de estatística**, substituindo
`ExamList`/`ExamDetail` por `exam-catalog-sidebar.tsx` (categorias + espécies), `exam-stat-cards.tsx`
(exames ativos, ticket médio, última atualização) e `exam-table.tsx`.

**3. Importação de CSV implementada de ponta a ponta.** Backend: `ImportExamsUseCase`
(`backend/app/modules/catalog/application/import_exams.py`) valida cada linha (categoria e
espécie por **nome**, não UUID; código duplicado no arquivo ou já no banco; preço e adicional de
plantão) e persiste em uma única transação **só as linhas válidas**, sem interromper por causa de
uma linha inválida — mesmo padrão de "erro por linha sem interromper as demais" já exigido pela
spec original. Endpoint `POST /api/v1/exams/import` (multipart, `catalog.manage`), auditoria
`exams.imported` por exame criado. Frontend: `exam-import-button.tsx` faz upload e mostra
`imported_count` + lista de erros por linha.

**4. Formato de CSV definido nesta entrega, não documentado em `spec-pages.md`.** Colunas:
`code,name,description,category,price_base,plantao_surcharge_fixed,plantao_surcharge_percent,species,active`.
`category` e `species` são **nomes**, não IDs (mais editável à mão numa planilha); `species`
aceita múltiplos valores separados por `;`. Categoria ou espécie desconhecida é erro de linha —
**nunca** criação implícita de cadastro relacionado (proibição explícita do `CLAUDE.md`).

**5. Filtro de espécie na sidebar é seleção única**, não múltipla como o mockup sugere
visualmente. `GET /exams` só aceita um `species_id` por vez — implementar seleção múltipla exigiria
mudar o contrato da API (`species_ids: list[UUID]` + lógica OU/E a decidir) sem que nenhuma spec
peça isso. Documentado como simplificação deliberada, não descoberto silenciosamente.

**6. Contagens, filtro e estatísticas são inteiramente client-side**, calculados sobre a página já
carregada (`useExamsQuery({ search, pageSize: 100 })`), sem endpoint de agregação novo. Escolha
deliberada para não introduzir um endpoint especulativo sem medição de necessidade real — ver
pendência correspondente abaixo.

**7. "Última atualização" mostra só a data, sem autor.** O mockup mostra data **e** nome de quem
atualizou (ex.: "Fabianna G."). `Exam.updated_by` existe (UUID), mas não há endpoint de
resolução de nome de usuário disponível para esta feature consumir — construir um agora seria
escopo novo (integração com o módulo de usuários) não pedido. Card mostra só a data.

## Alternativas consideradas

- **Placeholder estático para parâmetros de laudo / prazo de entrega / taxas de plantão** —
  rejeitada pelo usuário (opção oferecida explicitamente em `AskUserQuestion`, resposta:
  "omitir entirely" para os três). Um placeholder cosmético sem dado real correria o risco de ser
  lido como funcionalidade implementada.
- **Espécie multi-select real na sidebar**, mudando `GET /exams?species_id=` para aceitar lista —
  rejeitada por escopo: mudaria contrato de API existente e exigiria decidir semântica OU/E sem
  pedido explícito; adiada até haver necessidade real.
- **Endpoint de agregação (`GET /exams/stats`) para contagens/ticket médio no catálogo inteiro** —
  rejeitada por YAGNI nesta entrega: o volume atual do laboratório cabe em uma página de 100
  itens; construir agregação server-side sem medir se o limite de 100 é realmente atingido seria
  otimização especulativa (regra de performance: "cache só depois de medir").
- **Import síncrono linha-a-linha com commit parcial (savepoint por linha)** — rejeitada em favor
  de validar tudo em memória primeiro e persistir só o conjunto válido em uma transação única:
  mais simples, sem depender de savepoints do driver, e o resultado observável (parcial, com
  relatório de erro) é o mesmo.

## Consequências — pendências explícitas

Estas são as lacunas que ficam **abertas de propósito** depois desta entrega, para não virarem
suposição silenciosa depois:

1. **Parâmetros de laudo (faixa de referência por espécie/idade) seguem sem nenhum modelo de
   domínio.** Quando o núcleo (atendimento + fechamento) estiver estável e a prioridade chegar ao
   domínio de Laudo (P1), isso precisa de ADR próprio — provavelmente uma entidade nova
   referenciando `Exam` por ID, não um campo dentro dele.
2. **"Prazo de entrega" não existe em `Exam`.** Se vier a ser pedido, é campo novo aditivo
   (nullable, sem backfill necessário) — mas fica registrado aqui que o mockup já o sugeriu e foi
   conscientemente descartado, para não ser reintroduzido "silenciosamente" numa fatia futura sem
   ADR.
3. **Painel de taxas de plantão (global, normal/especial) não tem agregado próprio.** É uma
   configuração de laboratório, não de exame — precisa de módulo e ADR dedicados antes de existir
   em qualquer tela.
4. **Formato de CSV (item 4 da Decisão) foi inventado nesta entrega, sem confirmação prévia do
   usuário sobre o layout de colunas.** Se o laboratório já tiver uma planilha real de catálogo
   (mencionada em conversas anteriores — há um arquivo `.xlsx` de controle no repositório), o
   formato de colunas adotado aqui pode não bater com o dela. **Ação pendente**: validar o layout
   de colunas contra a planilha real antes de comunicar este import como pronto para uso em
   produção.
5. **Contagens/filtro/estatísticas do catálogo quebram silenciosamente acima de 100 exames**
   (`pageSize: 100` fixo, sem paginação real na tela). Não há aviso na UI quando isso acontece —
   o usuário simplesmente veria contagens/média que não refletem o catálogo inteiro. **Ação
   pendente**: decidir o gatilho (ex.: acima de N exames cadastrados) para trocar por endpoint de
   agregação server-side, antes que o catálogo real do laboratório passe de 100 itens.
6. **Autor da última atualização não é exibido** — só a data. Resolver exige expor um lookup de
   nome de usuário por ID a esta feature (hoje inexistente), que é escopo de outra fatia.
7. **Filtro de espécie é seleção única**, divergindo visualmente do mockup (que sugere múltipla).
   Se isso for cobrado como requisito real (não só estético), precisa de ADR próprio para decidir
   o contrato de API (`species_ids` + semântica OU/E) antes de implementar.
8. **Busca da lista dispara uma requisição por tecla digitada, sem debounce** — mesmo padrão já
   presente em Pacientes, Clínicas e Veterinários (não é regressão desta entrega, é lacuna
   pré-existente em todas as telas de lista do app). Registrado aqui porque foi observado durante
   a verificação desta tela, mas a correção é transversal — não deveria ser feita só neste módulo
   sem decisão de aplicar às demais.
9. **Nenhum cenário de concorrência real foi testado para o import de CSV** (duas importações
   simultâneas com códigos sobrepostos). O `UNIQUE` de `exams.code` no banco garante que a segunda
   falha em vez de duplicar, mas o comportamento de erro nesse cenário (a linha aparece como
   "importada" na resposta da primeira requisição e como "código já cadastrado" na segunda, ou
   as duas colidem em `IntegrityError` não mapeado) não foi exercitado por teste de concorrência
   real (`.claude/rules/testing.md` exige isso para fluxo com concorrência real) — fica como
   lacuna de cobertura, não como bug confirmado.

## Consequências — o que já foi corrigido, não é pendência

- **Bug real encontrado na verificação manual em Chrome**: o card "Ticket médio" incluía exames
  inativos na média, ficando inconsistente com "Exames ativos" ao lado (inativar um exame não
  mudava a média). Corrigido no mesmo commit desta fatia — `pricedExams` agora filtra
  `status === 'ACTIVE'` — com teste de regressão (`exams-page.test.tsx`, "average ticket excludes
  inactive exams from the calculation").
- `exam-list.tsx`/`.css` e `exam-detail.tsx`/`.css` removidos por ficarem órfãos (nenhum import
  restante), evitando dead code.

## Verificação

Suíte automatizada verde antes da entrega: backend (Ruff + mypy estrito em `domain`/`application`
+ pytest — 28 testes unitários e 17 de integração no módulo `catalog`, incluindo import parcial
com erro por linha, permissão e rejeição de arquivo não-CSV, contra PostgreSQL real via
Testcontainers); frontend (`tsc -b` + oxlint + vitest — 15 testes no catálogo, incluindo
navegação entre lista e form dedicado, filtro por categoria/espécie, ocultação de preço sem
`pricing.read`, import com relatório de erro — `vite build` de produção ok).

**Verificação manual em 2026-07-26**, Postgres local, backend e frontend rodando, logado como
usuário `SUPER_ADMIN` de teste, testado no Chrome: criação de categoria inline, criação e edição
de exame pela tela dedicada, inativação via menu da linha, filtro por categoria e por espécie,
busca por nome, importação de CSV com 1 linha válida + 1 linha com categoria inexistente
(relatório de erro correto), rejeição de arquivo não-CSV, e bloqueio de código duplicado (`409`)
exibido no formulário. Nenhum erro de console ou requisição falha atribuível a este código; o bug
do "Ticket médio" (acima) foi o único encontrado, e já corrigido antes desta entrega ser dada como
concluída. Dado de teste removido ao final da verificação.

## Complemento — 2026-08-12: código automático

Criações comuns de exame deixaram de aceitar código fornecido pelo cliente. O servidor gera oito
caracteres alfanuméricos maiúsculos com fonte criptograficamente segura, verifica unicidade e
retenta colisões; o código não pode ser alterado depois. A importação CSV permanece separada e
preserva seus códigos externos, pois eles participam da reconciliação do arquivo. A restrição
única em `exams.code` continua sendo a garantia final contra colisões concorrentes.
