# Análise da Planilha Operacional do Vertere Lab

## 1. Visão geral

A planilha atual funciona como cadastro mestre e livro operacional de atendimentos. Ela cumpre o papel de um sistema transacional, mas sem garantias de integridade, histórico, autorização, rastreabilidade ou colaboração simultânea segura.

### Estrutura encontrada

| Aba | Finalidade | Volume observado |
|---|---|---:|
| Cadastro Clínicas | Cadastro de clientes institucionais | 40 clínicas |
| Cadastro Veterinários | Profissionais vinculados a clínicas ou autônomos | 147 veterinários |
| Dados | Registro de protocolos, pacientes, exames e valores | 1.794 registros operacionais válidos |
| Suporte | Listas auxiliares | 5 grupos de domínio |

### Período analisado

- primeiro atendimento: 03/01/2026;
- último atendimento preenchido: 30/05/2026;
- dias com movimento: 145;
- média: aproximadamente 12,4 registros por dia ativo;
- pico observado: 29 registros em um dia.

### Volume e concentração

- 27 clínicas tiveram movimento no período;
- 86 veterinários aparecem nos atendimentos;
- aproximadamente 1.564 combinações distintas de paciente e proprietário;
- as duas clínicas de maior volume concentram cerca de 67% dos registros;
- a clínica de maior volume sozinha representa aproximadamente 52%.

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

A soma dos 1.794 registros operacionais válidos é R$ 185.017,00. O total exibido na planilha é R$ 185.117,00. A diferença de R$ 100,00 vem de um valor residual em uma linha sem atendimento.

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
- a soma financeira dos registros importados corresponder à soma validada de R$ 185.017,00, salvo ajustes aprovados;
- nenhuma clínica ou veterinário for criado silenciosamente por aproximação incerta;
- todo conflito estiver em relatório de exceções;
- protocolos forem únicos;
- relatórios de duplicidade e campos ausentes forem entregues;
- o lote puder ser reprocessado sem duplicar dados.
