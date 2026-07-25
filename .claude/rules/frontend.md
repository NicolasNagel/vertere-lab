---
# Regras de frontend — carrega ao tocar código React/TypeScript ou ao consultar a referência
# visual das telas (mockup HTML + spec).
paths:
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
  - "assets/features/screens/**"
---
# Regras de Frontend — React

## Estrutura
- Organize por feature/domínio: `app` compõe providers e rotas; `features` contém caso de
  interação (`features/attendances`, `features/billing`); `entities` contém modelo de
  apresentação; `shared` é UI/utilidade genérica.
- Não crie uma pasta `services/` global sem limite — cada feature tem o que precisa.

## Dados
- **TanStack Query** para todo estado de servidor. Chave de query inclui o escopo necessário
  (`["attendances", clinicId, filters]`); invalide após mutação.
- Estado local (`useState`) só para interação de UI, nunca para dado de servidor.
- Não duplique cache em Context e Query ao mesmo tempo.
- Optimistic update só quando reversível com segurança.
- Limpe dado ao trocar escopo (troca de clínica) ou logout — dado da clínica A não pode
  sobreviver na tela depois de trocar para a clínica B.

## Formulários
- **React Hook Form** + Zod para feedback local — mas **o backend é a autoridade final**; Zod
  nunca substitui a validação Pydantic.
- Preserve rascunho em erro recuperável; previna double submit.
- Envie `Idempotency-Key` em mutação crítica (confirmar atendimento, fechar competência).
- Máscara de exibição é separada do valor canônico armazenado.
- Erro de campo (validação) e erro de domínio (regra de negócio) são visualmente distintos.

## Registro de Atendimento (tela crítica)
- Fluxo orientado a teclado — recepção usa isso o dia inteiro.
- Criação rápida de cadastro (proprietário/paciente novo) **não perde o rascunho** do atendimento.
- Busca mostra duplicidade provável antes de deixar criar.
- Resumo financeiro vem do backend, nunca calculado só no navegador.
- Tela de confirmação mostra clínica, veterinário, paciente, exames e total antes do commit.
- Conflito de versão oferece **recarregar**, nunca sobrescreve silenciosamente.
- Status e bloqueio financeiro sempre visíveis — botão oculto não é autorização (a autoridade é
  sempre o backend).

## Fechamento
- Prévia distingue visualmente elegível, bloqueado, cancelado e ajustado.
- Confirmação de fechamento é um passo explícito, não um clique acidental.
- Reabertura exige motivo digitado, não só um toggle.
- Exportação usa o snapshot, não recalcula no cliente.

## Segurança
- Nunca guarde refresh token em `localStorage`.
- Nenhum segredo no bundle do frontend.
- `401` (não autenticado) e `403` (sem permissão) tratados como casos diferentes na UI.
- Evite PII em analytics; sanitize conteúdo antes de renderizar.

## Acessibilidade
Navegação por teclado, foco visível, labels em todo campo, mensagem de erro associada ao campo,
contraste adequado, semântica HTML correta, nunca depender só de cor para transmitir estado.
Fluxo crítico (atendimento, fechamento) tem teste de acessibilidade automatizado.

## Performance
Code splitting por rota quando o ganho for medido; evite waterfall de requisição desnecessário;
virtualização de lista só com medição prévia; debounce em busca sem atrasar a seleção; cancele
request obsoleto ao digitar de novo.

## Implementação a partir de referência visual (mockup HTML)
> Aplica-se sempre que a tarefa for "implemente esta tela" a partir de um HTML/mockup fornecido
> como referência. Esta seção cobre só o que é **específico desse tipo de tarefa** — todo o
> resto (estados, formulário, acessibilidade, dado de servidor) já está definido acima e não é
> repetido aqui.

### Onde está a referência
- Mockups HTML de cada tela: `assets/features/screens/`.
- `assets/features/screens/spec-pages.md` — leia **sempre junto** com o HTML da tela antes de
  começar a análise abaixo. Quando o spec e o HTML divergirem (texto diz uma coisa, mockup mostra
  outra), trate como comportamento não especificado (item 8 da análise) — não escolha um dos
  dois silenciosamente, sinalize a divergência.
- Tela nova sem entrada correspondente no `spec-pages.md`: trate o HTML sozinho como referência
  visual, mas marque explicitamente na análise que não há spec textual — o texto de apoio existe
  precisamente para reduzir esse tipo de suposição.

### O mockup é referência visual, não código a herdar
- O HTML fornecido mostra **como deve parecer**, não como deve ser estruturado. Não copie o
  documento inteiro para um componente único, não preserve `style` inline, `id`/classe do mockup
  ou markup que não seria natural em React.
- Reutilize os tokens de design e componentes compartilhados que já existem em `shared/` antes de
  criar algo novo — o mockup existir com uma cor/espaçamento específico não autoriza reinventar
  um token que já tem equivalente no design system.
- Divergiu do padrão visual já estabelecido no restante do app? Justifique a divergência
  explicitamente na entrega — não replique silenciosamente um detalhe do mockup que quebra a
  consistência com o resto do sistema.

### Análise obrigatória antes de escrever qualquer código
Antes do primeiro componente, produza (e mostre) esta análise:
1. estrutura visual da tela e hierarquia de seções;
2. componentes reutilizáveis identificados (existentes em `shared/` ou novos candidatos);
3. tokens de design já existentes que se aplicam (cor, espaçamento, tipografia — não invente
   novo token sem checar se já existe um);
4. campos, ações e estados da interface (loading, erro, vazio, sucesso, desabilitado — ver
   "Acessibilidade" acima para o padrão já exigido);
5. dependências de API que a tela vai precisar (endpoint, ainda que só o nome esperado);
6. permissões necessárias para cada ação visível (ver `07-auth-security-lgpd.md` — lembrando que
   botão oculto nunca é controle de autorização, só UX);
7. **dado demonstrativo do mockup que não pode virar valor hardcoded** — nome de paciente,
   clínica, veterinário, exame ou preço que aparece no HTML de exemplo é sempre dado fictício de
   protótipo; vira prop/estado vindo de API real, nunca literal no componente;
8. comportamento que o mockup não especifica (o que acontece ao errar, ao não ter permissão, ao
   ter lista vazia) — **liste como pendência explícita, não invente silenciosamente**. Isso é o
   mesmo princípio de "não assumir sem sinalizar" do `CLAUDE.md`, aplicado a mockup.

### Ordem de entrega
Ao implementar uma tela a partir de referência visual, entregue nesta ordem: (1) a análise acima;
(2) árvore de componentes; (3) contratos TypeScript (props, DTOs de API esperados); (4) estrutura
de arquivos dentro da feature; (5) implementação; (6) testes; (7) pendências de integração com o
backend (endpoint que ainda não existe, contrato não confirmado); (8) critérios de aceite. Pular
direto para a implementação sem mostrar os passos 1-4 é o padrão que esta seção existe para
evitar — é aqui que a alucinação de campo/endpoint/comportamento inexistente costuma entrar.