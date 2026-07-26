# ADR-003 — Veterinários: CRMV sem checksum, layout mestre-detalhe (não o grid do mockup)

- **Status**: aceita
- **Data**: 2026-07-25
- **Decisores**: Nicolas Nagel (PO/dev), Claude (execução)

## Contexto

Fase 2 do roadmap (`docs/05-roadmap-backlog.md` §4), item 2 — cadastro de Veterinários, seguindo
o mesmo padrão já estabelecido pelo módulo Clínicas (`ADR-002`). Duas decisões precisaram ser
tomadas sem resposta pronta em `docs/`:

1. **Formato do CRMV.** `assets/features/screens/spec-pages.md` (Tela de Cadastro de
   Veterinários) exige CRMV obrigatório e único, mas não define formato, faixa de dígitos nem
   algoritmo de validação — diferente do CNPJ, que tem um dígito verificador público e
   amplamente documentado. O CRMV é emitido por conselho regional (CRMV-SC, CRMV-SP, ...) e cada
   estado tem sua própria numeração; não existe um único algoritmo de checksum nacional.
2. **Layout da tela.** O mockup (`assets/features/screens/8-cadastro-veterinarios.html`) mostra
   um grid de cards em 3 colunas com abas de filtro (Todos/Vinculados/Autônomos) — um padrão de
   interação diferente do mestre-detalhe (lista + painel lateral) já usado e testado na tela de
   Clínicas para o mesmo tipo de cadastro estruturante.

Se nada fosse decidido, ficaria ambíguo (a) se CRMV deveria ganhar uma validação de formato
inventada sem base documental, arriscando rejeitar CRMVs reais válidos, e (b) se cada tela de
cadastro deveria replicar fielmente seu próprio mockup mesmo divergindo do padrão de interação já
estabelecido no resto do app — o que fragmentaria a experiência entre telas irmãs.

## Decisão

**CRMV**: tratado como string obrigatória, normalizada (espaços colapsados, maiúsculas) e única
(`Crmv` value object em `backend/app/modules/veterinarians/domain/value_objects.py` + constraint
`UNIQUE` no banco). Nenhuma validação de dígito verificador ou de formato por UF é aplicada nesta
fatia.

**Layout**: a tela de Veterinários (`frontend/src/features/veterinarians/`) usa o mesmo padrão
mestre-detalhe de `ClinicsPage` (busca + lista + painel de detalhe/formulário), não o grid de
cards com abas do mockup. As abas "Todos/Vinculados/Autônomos" do mockup viraram botões de filtro
acima da lista, com o mesmo papel funcional.

## Alternativas consideradas

- **Validar CRMV com um formato fixo (ex.: regex `UF-\d{4,6}`)** — rejeitada: nenhuma fonte do
  projeto (PRD, spec, modelo de domínio) documenta o formato oficial por estado, e uma regex
  inventada arriscaria bloquear CRMV reais no primeiro cadastro real do laboratório. Fica como
  pendência explícita para quando o time confirmar o formato exato.
- **Replicar o grid de cards com abas do mockup literalmente** — rejeitada: introduziria um
  segundo paradigma de navegação só para esta tela, quebrando a consistência que a regra de
  mockup (`.claude/rules/frontend.md`, "Implementação a partir de referência visual") pede para
  justificar antes de adotar. O mockup é referência visual de conteúdo/tokens, não a estrutura de
  interação a herdar.

## Consequências

- CRMV duplicado com variação de espaçamento/maiúsculas (`"crmv-sc 04567"` vs.
  `"CRMV-SC   04567"`) é corretamente detectado como o mesmo CRMV, mas um erro de digitação real
  (número trocado) não é pego na entrada — só na duplicidade, se já existir outro igual. Cobertura
  de teste: `test_create_veterinarian_normalizes_crmv_before_duplicate_check` (backend).
- Se o time confirmar depois um formato oficial (ex.: exigir prefixo `CRMV-UF`), a mudança é
  aditiva na validação do `Crmv` value object, sem migração de dado necessária além de eventual
  normalização de registros já existentes fora do novo formato.
- Toda tela de cadastro estruturante futura (proprietários, pacientes, catálogo) deve, por
  padrão, seguir o mesmo mestre-detalhe — um mockup que proponha um layout diferente exige
  justificativa explícita na entrega, não adoção automática.
- Campo "Clínica(s) vinculada(s)" (obrigatório se não autônomo, per spec) **não está
  implementado** nesta fatia — é a Fatia 3/4 do plano aprovado (vínculo N:N veterinário-clínica).
  A validação "não autônomo exige ao menos uma clínica" também fica pendente até lá; o formulário
  mostra o campo desabilitado com aviso explícito em vez de fingir que a regra já é aplicada.

## Complemento — 2026-07-25: vínculo N:N veterinário-clínica (Fatia 3/4)

Fecha a pendência acima. Três decisões adicionais, sem resposta pronta em `docs/`:

**1. Onde vive o vínculo.** Criado um módulo novo e neutro,
`backend/app/modules/veterinarian_clinics/` (domain/application/infrastructure), em vez de
colocar a entidade de vínculo dentro de `veterinarians` ou `clinics`. Alternativa rejeitada:
hospedar dentro de um dos dois módulos existentes obrigaria o outro a importar esse módulo
(ex.: `clinics` importando de `veterinarians` para ler vínculos na tela de Clínica), invertendo a
direção de dependência entre dois agregados pares sem motivo — o vínculo é simétrico por natureza
(nenhum dos dois "possui" o outro).

**2. De qual lado a escrita acontece.** A spec (`spec-pages.md`, telas de Clínicas e
Veterinários) descreve endpoints de escrita só do lado de Clínica
(`POST/DELETE /clinics/{id}/veterinarians`) e diz que o vínculo deve "refletir também no cadastro
do veterinário (bidirecional)". Implementei a escrita **apenas do lado do Veterinário**
(`POST/DELETE /veterinarians/{id}/clinics`), porque a Fatia 4 (frontend) constrói a UI de gestão
na tela de Veterinários, não na de Clínicas — a tela de Clínicas ganhou só a **leitura** do
vínculo (card "Veterinários vinculados", somente exibição, sem ação de vincular/desvincular a
partir dali). Isso é uma redução de escopo deliberada, não um esquecimento: os nomes de permissão
da spec para a tela de Clínicas (`CLINIC_EDIT` para "criar/editar/vincular") ficam sem uso — o
vínculo usa `veterinarians.manage`, seguindo a convenção real do catálogo de permissões (mesmo
padrão de divergência já registrado acima para `VET_VIEW`/`VET_EDIT`). Se um dia for necessário
gerenciar o vínculo a partir da tela de Clínica também, os casos de uso
(`LinkVeterinarianToClinicUseCase`/`UnlinkVeterinarianFromClinicUseCase`) já são reutilizáveis sem
mudança — só falta expor os endpoints espelhados em `clinics/api/routers.py`.

**3. Onde a regra "não autônomo exige ≥1 clínica" é aplicada.** Só no **unlink** (bloqueia
remover a última clínica de um veterinário não autônomo, `LastClinicLinkRequiredError` → `409`) e
como **validação client-side** no formulário de criação (Zod/estado local exige seleção antes do
submit). **Não existe gate no backend no momento da criação** — `CreateVeterinarianUseCase`
(Fatia 1) não foi alterado para aceitar `clinic_ids` nem para recusar `is_autonomous=false` sem
vínculo. Isso significa que é tecnicamente possível, hoje, criar um veterinário não autônomo sem
nenhuma clínica vinculada usando a API diretamente (fora da UI) — a UI guia o fluxo correto, mas
o backend não fecha esse buraco na ponta de criação, só na de remoção. Rejeitei fechar isso agora
porque exigiria tornar `CreateVeterinarianUseCase` transacionalmente ciente de `Clinic` e do
módulo de vínculo (múltiplos agregados na mesma escrita), uma mudança de contrato da Fatia 1 fora
do escopo combinado para esta fatia. Fica registrado como dívida técnica explícita, não como
critério de aceite silenciosamente considerado cumprido.

Decisões menores: `primary_clinic` é um boolean simples por vínculo; linkar com `primary=true`
desmarca automaticamente qualquer principal anterior do mesmo veterinário (`clear_primary_for_veterinarian`),
evitando duas clínicas "principais" ao mesmo tempo. Link e unlink são idempotentes (chamar de novo
não duplica nem falha) em vez de usar `Idempotency-Key` — não é uma mutação financeira/crítica na
acepção de `.claude/rules/backend.md`, então o padrão mais simples de "mesmo estado final = sucesso"
foi suficiente. `ON DELETE CASCADE` nas FKs de `veterinarian_clinics` é seguro porque
`veterinarians`/`clinics` nunca são apagados de verdade (só inativados) — o cascade só protege
contra linha órfã em caso de exclusão de rascunho, nunca contra perda de histórico real.

### Verificação (Fatia 3/4)

Backend: 97 testes verdes (81 anteriores + 16 novos — 11 unitário/5 integração do módulo de
vínculo), ruff + mypy limpos, migration `0006_create_veterinarian_clinics` testada em banco vazio
via Testcontainers. Frontend: 45 testes verdes (42 anteriores + 3 novos cobrindo bloqueio de
criação sem clínica, criação com vínculo automático, e desvínculo pelo card de detalhe), `tsc -b`
+ oxlint + `vite build` limpos.

Verificação manual em 2026-07-25, Postgres local, backend e frontend rodando, logado como usuário
real, testado no Chrome:
- Criar veterinário não autônomo (`Karin Witt`, `CRMV-SC 04127`) marcando a clínica "Reale" no
  formulário → `POST /veterinarians` (`201`) seguido automaticamente de
  `POST /veterinarians/{id}/clinics` (`204`, `primary: true`) — vínculo criado na mesma operação
  percebida pelo usuário, sem etapa manual extra.
- Detalhe do veterinário mostra "Reale" com badge "Principal" e ação "remover".
- Detalhe da clínica "Reale" reflete o vínculo (leitura): "Karin Witt · CRMV-SC 04127 ·
  PRINCIPAL", confirmando a bidirecionalidade pedida pela spec.
- Tentativa de remover o único vínculo de um veterinário não autônomo → `409 Conflict` real do
  backend, com a mensagem "Não foi possível remover o vínculo. Veterinário não autônomo precisa
  de ao menos uma clínica." exibida na UI — a regra central desta fatia funciona ponta a ponta,
  não só nos testes automatizados.

## Complemento — 2026-07-26: gate de "não autônomo exige ≥1 clínica" fechado na criação

Fecha a dívida técnica registrada acima ("Onde a regra... é aplicada", item 3). Decisão de
desenho confirmada com o usuário: **payload único** em vez de duas chamadas orquestradas.
`POST /veterinarians` agora aceita `clinic_ids`/`primary_clinic_id` opcionais;
`CreateVeterinarianUseCase` valida (a) se não autônomo, `clinic_ids` não pode ser vazio, (b) cada
`clinic_id` existe, (c) `primary_clinic_id`, se informado, precisa estar em `clinic_ids` — tudo
antes de persistir, e os vínculos são criados na mesma transação (`uow`) do veterinário, não em
uma segunda chamada de API.

**Alternativas consideradas**: (1) manter duas chamadas com compensação no frontend se a segunda
falhasse — rejeitada, não fecha o buraco de criação direta via API sem UI; (2) adiar
indefinidamente — rejeitada, o usuário priorizou fechar a lacuna nesta sessão.

**Consequência arquitetural**: `veterinarians.application.create_veterinarian` agora depende de
`clinics.domain.repositories` e `veterinarian_clinics.domain` — o objetivo original desta ADR de
"nem `veterinarians` nem `clinics` depende do outro" (linha 6) não vale mais para o caso de uso de
criação especificamente; o vínculo em si (`veterinarian_clinics`) continua em módulo neutro
próprio. Aceitável: é a mesma transação de negócio (criar veterinário com sua(s) clínica(s)), não
um acoplamento acidental.

**Efeito colateral corrigido junto**: `SqlAlchemyVeterinarianRepository.add()` não tinha
`session.flush()` — sem `relationship()` ORM entre `VeterinarianModel` e
`VeterinarianClinicModel`, o unit of work não infere a ordem de inserção sozinho, e criar os
vínculos na mesma transação batia em `IntegrityError` de FK. Mesmo problema já documentado para
`SqlAlchemyUserRepository.add()` (`HANDOFF.md`); corrigido com o mesmo padrão (`flush()` explícito
logo após o `add()`).

O frontend (`veterinarian-form.tsx`/`veterinarians-page.tsx`) foi atualizado para enviar
`clinic_ids`/`primary_clinic_id` na própria criação em vez de uma chamada `POST .../clinics` por
clínica selecionada — o card de vínculos no detalhe (adicionar/remover clínica depois de já
criado) continua usando os endpoints de link/unlink normalmente, só a criação inicial mudou.

### Verificação (complemento)

Backend: `ruff check` + `ruff format --check` + mypy estrito + pytest (16 unitário de
veterinarians + 9 integração de veterinarians + 5 integração de veterinarian_clinics, todos
verdes, incluindo os novos casos de criação sem clínica rejeitada com `422`, criação com clínica
vinculada automaticamente, e criação com múltiplas clínicas e principal explícito). Frontend:
`tsc -b` + oxlint + vitest (61 testes) + `vite build` de produção ok, incluindo o teste
atualizado que confirma `clinic_ids`/`primary_clinic_id` no corpo do `POST /veterinarians`.

Verificação manual no navegador **não repetida** para este complemento especificamente (a fatia
de vínculo já foi verificada manualmente antes — ver acima); a suíte automatizada cobre o
caminho novo ponta a ponta via HTTPX/ASGI contra Postgres real.

## Verificação

Suíte automatizada verde antes da entrega: backend (`ruff check` + `ruff format --check` + mypy
estrito em `domain`/`application` + pytest — 51 unitário + 30 integração com Postgres real via
Testcontainers, incluindo o teste de schema `test_alembic_upgrade_head_runs_on_empty_database`
atualizado para a nova tabela `veterinarians`); frontend (`tsc -b` + oxlint + vitest — 42 testes,
`vite build` de produção ok).

Verificação manual em 2026-07-25, com Postgres local (`docker-compose up -d postgres`), migração
`0005_create_veterinarians` aplicada, backend e frontend rodando, logado como usuário real,
testado no Chrome:
- Criar veterinário (`Dra. Fabianna Garcia`, `CRMV-SC 04567`) → `201 Created`, painel de detalhe
  atualizado com nome, CRMV e status "Ativo" corretos.
- Lista mostra a linha recém-criada com status, CRMV e telefone.
- Inativar via menu "Mais ações" → `200 OK`, badge muda para "Inativo", registro preservado (não
  removido) — condizente com `.claude/rules/product-domain.md`, "Inative em vez de apagar".
- Ação "Novo vet"/"Editar" ocultas corretamente sem `veterinarians.manage` (verificado nos testes
  de componente com MSW, não observado manualmente com um segundo usuário nesta sessão — backend
  já testado em `test_create_veterinarian_without_permission_is_forbidden`).
