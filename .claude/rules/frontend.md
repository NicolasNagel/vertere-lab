---
# Regras de frontend — carrega ao tocar código React/TypeScript.
paths:
  - "frontend/**/*.ts"
  - "frontend/**/*.tsx"
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