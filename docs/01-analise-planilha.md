# Análise da Planilha Operacional do Vertere Lab

> Recalculado em 2026-07-28 contra `PLANILHA DE CONTROLE 2026 - VERTERE LAB (4).xlsx` (a versão
> (3), com 1.794 registros, foi a base da análise original — o usuário atualizou o arquivo com
> mais atendimentos desde então). Estrutura das abas e problemas de qualidade descritos abaixo
> continuam os mesmos; os números de volume foram atualizados para a versão (4). Se o arquivo for
> atualizado de novo, recalcule antes de usar estes números como alvo de reconciliação.

## 1. Visão geral

A planilha atual funciona como cadastro mestre e livro operacional de atendimentos. Ela cumpre o papel de um sistema transacional, mas sem garantias de integridade, histórico, autorização, rastreabilidade ou colaboração simultânea segura.

### Estrutura encontrada

| Aba | Finalidade | Volume observado |
|---|---|---:|
| Cadastro Clínicas | Cadastro de clientes institucionais | 40 clínicas |
| Cadastro Veterinários | Profissionais vinculados a clínicas ou autônomos | 150 veterinários |
| Dados | Registro de protocolos, pacientes, exames e valores | 2.497 registros operacionais válidos |
| Suporte | Listas auxiliares | 5 grupos de domínio |

### Período analisado

- primeiro atendimento: 03/01/2026;
- último atendimento preenchido: 19/07/2026;
- dias com movimento: 193;
- média: aproximadamente 12,9 registros por dia ativo;
- pico observado: 35 registros em um dia.

### Volume e concentração

- 28 clínicas tiveram movimento no período;
- 91 veterinários aparecem nos atendimentos;
- aproximadamente 2.102 combinações distintas de paciente e proprietário;
- as duas clínicas de maior volume concentram cerca de 65% dos registros;
- a clínica de maior volume sozinha representa aproximadamente 50%.

Esse padrão exige que o sistema suporte picos e grande assimetria de uso entre clientes, sem permitir que uma clínica acesse dados de outra.

## 2. Problemas de qualidade e riscos operacionais

### 2.1 Cadastro sem identificadores estáveis

Clínicas, veterinários, pacientes e proprietários são referenciados por texto. Isso produz variações de caixa, acento e escrita, por exemplo nomes de clínicas equivalentes escritos de formas diferentes.

Consequências:

- duplicidade aparente;
- dificuldade de consolidação;
- vínculos frágeis;
- risco de envio de laudo ao destinatário errado;
- impossibilidade de auditoria confiável.

### 2.2 Proprietário misturado com códigos e observações

Em 885 registros o campo de proprietário contém informações entre parênteses. Em 807 registros aparece `NI` no conteúdo. Nome, possível código do cliente e ausência de informação estão no mesmo campo textual.

O novo sistema deve separar:

- proprietário/tutor;
- documento ou código externo;
- telefone;
- e-mail;
- observação;
- indicador de dado não informado.

### 2.3 Pacientes sem identidade longitudinal

O paciente é apenas um nome associado à linha do exame. Não há identificador durável, histórico consolidado, data de nascimento, espécie padronizada ou vínculo confiável com o proprietário.

Há registros sem paciente, espécie, sexo, raça, idade ou proprietário. O sistema deve permitir dados incompletos somente quando a regra clínica admitir, registrando o motivo e o usuário responsável.

### 2.4 Catálogo de exames em texto livre

Foram encontradas 180 descrições diferentes de exames. Há variações de espaço, abreviação, composição e grafia, incluindo combinações como check-ups com urinálise, perfis, pesquisas e exames adicionais.

O sistema precisa de:

- categoria de exame;
- exame individual;
- painel/perfil composto;
- itens do painel;
- material biológico exigido;
- método;
- prazo estimado;
- unidade de medida e referência quando aplicável;
- instruções pré-analíticas;
- status ativo/inativo;
- versão do exame.

### 2.5 Preço não versionado

Pelo menos 24 descrições idênticas de exame apresentam mais de um preço-base. Isso pode refletir reajuste, condição comercial, clínica específica ou erro de preenchimento.

O preço não deve ficar apenas no cadastro atual do exame. Cada item do protocolo deve armazenar um snapshot imutável de:

- preço de tabela;
- desconto;
- adicional;
- preço final;
- tabela de preço utilizada;
- vigência;
- usuário ou regra que alterou o valor.

### 2.6 Total financeiro inconsistente

A soma dos 2.497 registros operacionais válidos é R$ 250.060,00. O total exibido na planilha é R$ 250.160,00. A diferença de R$ 100,00 vem de um valor residual em uma linha sem atendimento — o mesmo problema descrito abaixo, reproduzido de forma idêntica na versão atualizada do arquivo.

O novo sistema deve impedir esse cenário por meio de:

- chaves estrangeiras;
- campos obrigatórios;
- transações;
- cálculos server-side;
- proibição de valores financeiros desacoplados de um item de protocolo;
- fechamento auditável.

### 2.7 Fórmulas frágeis

O número e o protocolo são calculados por sequência em linha. Há fórmulas residuais em linhas vazias e protocolos incompletos. A geração por `último número + 1` não é segura em uso concorrente.

O protocolo deve ser gerado no banco dentro de transação, com restrição única por ano e mecanismo resistente a concorrência.

### 2.8 Status e listas incompletos

Há veterinários sem status e valores de espécie com variação de capitalização. Campos essenciais são livres, embora exista uma aba de suporte.

Todo domínio finito deve usar enumeração controlada, tabela de domínio ou cadastro versionado. A interface nunca deve depender de digitação livre para status, espécie, sexo, método de coleta ou tipo de atendimento.

## 3. Mapeamento da planilha para o sistema

| Campo atual | Entidade futura | Tratamento |
|---|---|---|
| Clínica | `Clinic` | ID estável, CNPJ/CPF separado, status e contatos |
| Veterinário | `Veterinarian` + vínculo | CRMV normalizado e relação N:N com clínicas |
| Data/Hora | `AttendanceRecord.service_date` ou `requested_at` | timestamp com timezone |
| Nº/Protocolo | `AttendanceRecord` | sequência transacional por ano |
| Método de coleta | `CollectionMethod` | enum/cadastro controlado |
| Paciente | `Patient` | ID, espécie, raça, sexo e nascimento |
| Proprietário | `Owner` | entidade separada e deduplicável |
| Tipo de exame | `ExamCategory` | catálogo controlado |
| Exame | `Exam` ou `ExamPanel` | catálogo versionado |
| Tipo | `ServiceLevel` | normal/plantão, extensível |
| Valor/Desconto/Adicional | `AttendanceExam` | snapshot financeiro |
| Valor Total | cálculo | calculado no servidor e persistido de forma consistente |

## 4. Estratégia de migração

1. congelar uma cópia da planilha de origem;
2. importar para tabelas de staging sem transformar o conteúdo original;
3. criar uma chave `source_row_number` e um `import_batch_id`;
4. normalizar clínicas e criar mapa de aliases;
5. normalizar veterinários e CRMV;
6. separar proprietários, códigos e marcadores `NI`;
7. criar pacientes candidatos por clínica, proprietário e nome normalizado;
8. mapear exames livres para catálogo canônico;
9. criar tabela de exceções para registros ambíguos;
10. executar importação em dry-run;
11. reconciliar quantidade, valores e protocolos;
12. aprovar exceções com usuário responsável;
13. executar importação definitiva de forma idempotente;
14. manter rastreabilidade entre cada registro novo e a linha original.

## 5. Critérios de reconciliação

A migração só será aceita quando:

- 100% das linhas válidas tiverem estado final conhecido;
- a soma financeira dos registros importados corresponder à soma validada de R$ 250.060,00, salvo ajustes aprovados;
- nenhuma clínica ou veterinário for criado silenciosamente por aproximação incerta;
- todo conflito estiver em relatório de exceções;
- protocolos forem únicos;
- relatórios de duplicidade e campos ausentes forem entregues;
- o lote puder ser reprocessado sem duplicar dados.

## 6. Fase 4 — Migração do histórico de atendimentos (spec, ainda não implementada)

> Escrito em 2026-07-29. As Fases 1–3 (cadastros estruturantes: clínicas, veterinários, catálogo
> de exames, pacientes/proprietário) e a Fase 2b (tabela de preços vigente via PDF) já estão
> implementadas no módulo `backend/app/modules/imports/`. Esta seção é **só especificação** —
> importar o histórico financeiro completo da aba `Dados` como `AttendanceRecord` continua fora
> de ordem enquanto o fechamento mensal (`MonthlyClosure`) não tiver `close`/`adjust`/`reopen`
> implementados (`AGENTS.md` § "Prioridade de implementação" — atendimento e fechamento vêm antes
> de migração).

### 6.1 O que já existe hoje que muda o desenho original

Quando o plano desta fatia foi escrito, `AttendanceRecord` era só um rascunho (`DRAFT`, sem
itens, sem protocolo). Isso não é mais verdade: `app/modules/attendances/domain/entities.py` já
tem `AttendanceRecord.confirm()` funcional — snapshot de `AttendanceExam` (preço/nome
imutáveis), `protocol_year`/`protocol_sequence`/`protocol_number` transacionais,
`billing_competence` derivado de `service_date`, e um campo `monthly_closure_id` (ainda sempre
`None`, reservado para quando o fechamento existir). O que **ainda não existe**:
`MonthlyClosure.close()`/ajuste/reabertura (`app/modules/billing/` só tem `preview_closure.py` —
prévia, não fechamento de verdade) e nenhum endpoint que ligue um `AttendanceRecord` confirmado a
uma competência fechada. É esse último ponto que continua bloqueando a Fase 4 — não a falta de
snapshot ou protocolo, que já existem.

### 6.2 Transformação linha → `AttendanceRecord` + `AttendanceExam`

- Cada linha válida da aba `Dados` (linhas 5–2501, 2.497 registros na versão (4) — confirmado
  linha a linha nesta sessão via `xlsx_reader.read_workbook`, mesma ferramenta que já lê a
  planilha para as Fases 1–3) vira **um** `AttendanceRecord` com `status = COMPLETED` (o
  atendimento já aconteceu; não é um rascunho a confirmar por um usuário).
- Cada linha simples (sem `+`) vira um único `AttendanceExam`; linha combinada (`"Check-up 2 +
  Urinálise"`, ~191 ocorrências na versão (3), proporção equivalente esperada na (4)) vira **N**
  `AttendanceExam`, um por componente do split (ver 6.3).
- `exam_code`/`exam_name`/`price_base` do item são o snapshot **da tabela vigente na Fase 2b/2 no
  momento da importação**, não recalculado depois — mesma regra de qualquer outro
  `AttendanceExam` (`.claude/rules/12-attendance.md`).
- `protocol_number` da planilha (`Nº`/`Protocolo`, ex. `1/2026`) é preservado como referência
  histórica **num campo separado** (ex. `legacy_protocol_reference`) — nunca reaproveitado como o
  `protocol_year`/`protocol_sequence` transacional real, que deve ser gerado pela mesma sequência
  de banco usada por atendimento novo (senão dois protocolos "1/2026" existiriam: o legado e um
  novo, colidindo).
- `billing_competence` da linha migrada é a competência **real da data do atendimento**
  (`service_date.replace(day=1)`), não inferida de outra forma — mesma regra do atendimento
  normal.

### 6.3 Exame combinado — split proporcional (decisão já confirmada com o usuário nesta sessão)

Regra: separar a string por `+`, buscar `price_base` **atual** de cada exame componente no
catálogo, ratear o valor total da linha proporcionalmente ao peso de cada `price_base` (ajuste de
arredondamento centavo a centavo na última parcela, nunca deixando a soma dos itens divergir do
total original da linha — mesma invariante `grand_total = Σ item.total_amount` de qualquer
`AttendanceRecord`). Se qualquer componente do split não existir no catálogo (fora do que a Fase
2/2b já importou), a linha inteira cai em exceção manual — nunca cria exame novo nem improvisa
preço.

### 6.4 Casos especiais já identificados nesta análise

- **Linha `TOTAIS` / resíduo de R$ 100,00**: nunca vira item financeiro — é a causa raiz já
  documentada da divergência R$ 250.060,00 × R$ 250.160,00 (§2.6). Excluída explicitamente do
  range de linhas válidas (a exclusão já é natural: linha `TOTAIS` não tem `Clínica` real, então
  cai fora do filtro "linha com clínica válida" que Fase 1-3 já usa).
- **Linha 406 (versão (4) — confirmado via leitura direta do arquivo nesta sessão; era a linha
  402 na versão (3), só deslocada)**: `Valor - Desconto + Adicional ≠ Valor Total` (`Valor=113,00`,
  `Desconto=0`, `Adicional=0`, `Total=135,00` — diferença de R$ 22,00 sem explicação nos dados).
  Cai em exceção manual, nunca "consertada" assumindo qual dos dois números está certo.
- **Zero ou preço ausente na ocorrência**: mesmo tratamento já usado na Fase 2 (`price <= 0` vira
  "sem preço"), mas aqui o item individual da linha cai em exceção, não a linha inteira, já que
  as outras linhas do mesmo `AttendanceRecord` (se combinado) podem estar corretas.

### 6.5 Fechamento do período migrado

- Nenhum `MonthlyClosure` é criado como efeito colateral da importação — fechamento histórico só
  é criado **depois** da reconciliação completa (§5) e aprovação humana explícita, exatamente como
  qualquer fechamento novo.
- A soma dos `AttendanceExam.total_amount` de todos os registros migrados de uma competência deve
  bater com a soma validada daquele mês; toda diferença exige exceção formal aprovada.

### 6.6 Testes obrigatórios quando esta fatia for implementada

Além dos gates gerais (`.claude/rules/08-testing.md`) e dos específicos de atendimento
(`.claude/rules/12-attendance.md` — duplicidade por retry, protocolo sob concorrência real,
isolamento de tenant, snapshot, auditoria): idempotência do lote completo (reprocessar não
duplica `AttendanceRecord`/`AttendanceExam`), unicidade de protocolo novo mesmo com 2.497 linhas
concorrendo pela mesma sequência transacional, split proporcional fechando exatamente com o total
original da linha (property-based test — `Hypothesis`, mesmo padrão de `.claude/rules/08-testing.md`
para invariante financeira), linha 406 e linha `TOTAIS` caindo em exceção e nunca em dado
financeiro, e reconciliação de competência batendo com a soma validada por mês.
