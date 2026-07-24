# ADR-002 — Endereço embutido em `Clinic`, sem `ClinicContact` separado

- **Status**: aceita
- **Data**: 2026-07-24
- **Decisores**: Nicolas Nagel (PO/dev), Claude (execução)

## Contexto

A Fase 2 do roadmap (`docs/05-roadmap-backlog.md` §4) começa pelo cadastro de clínicas. O modelo
de domínio (`docs/03-modelo-de-dominio.md` §1, contexto Master Data) lista `Clinic` e
`ClinicContact` como entidades separadas, sugerindo que uma clínica poderia ter múltiplos
contatos/endereços associados por relação 1:N.

O mockup de referência (`assets/features/screens/7-cadastro-clinicas.html`) e a spec da tela
(`assets/features/screens/spec-pages.md`, "Tela de Cadastro de Clínicas") descrevem só **um**
endereço por clínica, embutido no mesmo formulário de cadastro geral (CEP, rua, número, bairro,
cidade, UF, complemento) — não há indício de UI para múltiplos endereços ou múltiplos contatos
por clínica. Nenhum critério de aceite do PRD ou da spec menciona esse requisito.

Se nada fosse decidido, a implementação ficaria ambígua entre seguir `docs/03` à risca (criar
tabela `clinic_contacts` com FK 1:N desde já, sem UI ou caso de uso que a use) ou seguir o mockup
(campos de endereço direto em `clinics`) sem registrar por quê — o que divergiria do documento de
domínio silenciosamente, violando a prática do projeto de nunca desviar de um documento de
referência sem decisão explícita.

## Decisão

**Endereço é um conjunto de colunas simples em `clinics`** (`address_zip_code`,
`address_street`, `address_number`, `address_neighborhood`, `address_city`, `address_state`,
`address_complement`), não uma entidade `ClinicContact` separada com tabela própria.

Isso vale só para esta fatia (Clínicas, Fase 2). Não é uma revogação de `docs/03` — é adiar a
entidade `ClinicContact` até que exista um requisito real de N contatos/endereços por clínica
(ex.: filial, contato financeiro separado do contato operacional). Quando esse requisito
aparecer, a migração é: criar `clinic_contacts`, migrar os dados hoje embutidos em `clinics` para
um registro primário, e então permitir N adicionais — sem quebrar o que já existe, já que os
campos atuais continuam válidos como "o contato principal".

## Alternativas consideradas

- **Criar `ClinicContact` desde já, com `Clinic` tendo exatamente 1 contato obrigatório** —
  rejeitada por YAGNI (`CLAUDE.md`, "Princípios de código"): adiciona uma tabela, um repositório,
  uma junção e uma camada de mapeamento extra para modelar uma cardinalidade (1:N) que nenhuma
  tela ou caso de uso usa hoje. Também obrigaria decidir agora regras que não têm resposta clara
  ainda (o que significa "contato principal"? pode haver zero contatos? edição de qual endereço
  aparece na listagem?) — perguntas que só fazem sentido responder quando o requisito for real.
- **Seguir `docs/03` e implementar N contatos desde já, com UI ainda não desenhada** —
  rejeitada: não há mockup nem spec para essa UI; construir uma tela do zero sem referência visual
  contraria o modo de trabalho do projeto (fatia pequena, checkpoint, base na spec existente).

## Consequências

- `docs/03-modelo-de-dominio.md` fica **desatualizado nesta fatia especificamente** — `Clinic`
  ganhou colunas de endereço que a lista de campos do documento não detalha, e `ClinicContact`
  segue listado mas não implementado. Isso é aceitável enquanto documentado aqui; se o documento
  de domínio for revisado formalmente, esta ADR deve ser referenciada.
- Nenhuma tabela de junção nova, nenhum caso de uso extra de "vincular contato" nesta fatia —
  reduz a superfície testada e revisada da fatia de Clínicas.
- Quando `ClinicContact` (ou necessidade equivalente) surgir com um requisito real, a migração de
  dados existentes é direta (uma linha de `clinic_contacts` por `Clinic` já cadastrada) — não é um
  redesenho, é uma extensão aditiva.
- Preço, protocolo, laudo e qualquer módulo futuro que referencie `Clinic` por ID continuam
  válidos sem mudança, já que o endereço não é referenciado por ID externo em nenhum lugar do
  sistema ainda.
