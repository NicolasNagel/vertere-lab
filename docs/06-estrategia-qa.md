# Estratégia de QA — Vertere Lab V2

## 1. Estratégia baseada em risco

Risco máximo:

1. acesso indevido;
2. cadastro mestre incorreto ou duplicado;
3. atendimento inconsistente;
4. preço ou total incorreto;
5. fechamento divergente;
6. alteração de histórico fechado;
7. migração incompleta.

Esses riscos bloqueiam release.

## 2. Ferramentas recomendadas

### Backend

- pytest;
- pytest-asyncio quando aplicável;
- Testcontainers ou PostgreSQL real isolado;
- factory_boy ou factories próprias;
- Hypothesis para propriedades financeiras e invariantes;
- coverage.py;
- HTTPX/ASGITransport para API.

### Frontend

- Vitest;
- Testing Library;
- MSW para simulação de contrato no teste de UI;
- Playwright para E2E.

### Qualidade estática

- Ruff;
- mypy;
- TypeScript strict;
- auditoria de dependências;
- secret scanning.

## 3. Pirâmide de testes

### Unitários

- regras de permissão;
- normalização;
- detecção de duplicidade;
- cálculo de preço;
- arredondamento;
- estados do atendimento;
- elegibilidade do fechamento;
- cálculo de fechamento;
- regras de ajuste e reabertura.

### Integração

- repositórios com PostgreSQL real;
- constraints;
- transações;
- sequência concorrente;
- idempotência;
- Alembic upgrade/downgrade quando suportado;
- autorização com dados reais;
- fechamento concorrente;
- outbox.

### API/contrato

- OpenAPI;
- request e response;
- códigos de erro;
- paginação;
- filtros;
- idempotency key;
- versionamento de concorrência;
- CORS e autenticação.

### E2E

1. admin cria usuário e atribui permissão;
2. recepção cria clínica/veterinário/proprietário/paciente;
3. recepção registra e confirma atendimento;
4. financeiro abre prévia;
5. financeiro fecha competência;
6. recepção tenta alterar valor e recebe bloqueio;
7. financeiro registra ajuste autorizado;
8. usuário de outra clínica tenta acessar e recebe negação.

## 4. Matriz de permissão

Para cada endpoint e ação:

- sem sessão;
- sessão expirada;
- usuário inativo;
- papel sem permissão;
- permissão correta em clínica errada;
- permissão correta no escopo correto;
- administrador do laboratório;
- alteração de papel durante sessão.

A UI não é evidência de segurança. O teste deve chamar a API diretamente.

## 5. Testes do Registro de Atendimento

### Validação

- clínica inexistente ou inativa;
- veterinário inexistente, inativo ou sem vínculo;
- paciente de outro proprietário;
- paciente de outra clínica quando a regra proíbe;
- exame inativo;
- preço sem vigência;
- lista vazia de exames;
- desconto acima da política;
- adicional negativo;
- datas inválidas;
- campos mínimos ausentes.

### Concorrência

- 50 confirmações simultâneas geram 50 protocolos únicos;
- duas atualizações com mesma versão produzem um conflito;
- duplo submit com mesma idempotency key gera um atendimento;
- mesma key com payload diferente gera conflito;
- cancelamento e fechamento simultâneos não corrompem dados.

### Snapshot

- mudar nome de exame não muda atendimento antigo;
- reajustar preço não muda atendimento antigo;
- inativar veterinário não remove histórico;
- merge de paciente mantém referência.

## 6. Testes de fechamento

- período vazio;
- competência já fechada;
- dois fechamentos simultâneos;
- atendimento cancelado;
- item cancelado;
- preço zero permitido ou proibido conforme regra;
- valor residual sem atendimento impossível por FK;
- soma de itens igual ao cabeçalho;
- arredondamento em múltiplos itens;
- desconto e adicional;
- item já associado a fechamento;
- atendimento retroativo;
- reabertura sem permissão;
- ajuste sem motivo;
- exportação compatível com snapshot;
- reprocessamento idempotente.

## 7. Propriedades financeiras

Usar testes baseados em propriedades para garantir:

- `grand_total = subtotal - discount_total + surcharge_total`;
- total nunca é NaN ou float;
- soma do fechamento é soma exata dos snapshots;
- ajuste não altera snapshot original;
- duas execuções idempotentes retornam o mesmo fechamento;
- nenhuma combinação válida gera valor negativo não permitido.

## 8. Testes de migração

- todas as linhas recebem status final;
- importação repetida não duplica;
- aliases resolvem de forma determinística;
- conflito não é resolvido por aproximação silenciosa;
- soma validada é reconciliada;
- valor residual sem atendimento é reportado, não importado;
- IDs de origem são preservados;
- dry-run não altera produção.

## 9. Performance

Cenários:

- login;
- busca de clínica;
- busca de proprietário e paciente;
- formulário com catálogo;
- confirmação concorrente;
- listagem paginada;
- prévia de fechamento;
- fechamento com volume superior ao atual;
- exportação.

Gates iniciais:

- erro inferior a 1% em carga nominal;
- p95 conforme PRD;
- ausência de N+1 crítico;
- locks curtos;
- conexões de banco estáveis no ambiente serverless;
- consulta crítica com plano conhecido.

## 10. Segurança

- IDOR/BOLA;
- escalação horizontal e vertical;
- brute force;
- enumeração de usuário;
- CSRF conforme autenticação;
- XSS;
- SQL injection;
- mass assignment;
- excesso de campos em response;
- logs com PII;
- token no localStorage quando proibido;
- sessão após inativação;
- upload e URL assinada em módulos futuros.

## 11. Dados de teste

- nunca usar cópia bruta de produção em CI;
- gerar ao menos duas clínicas;
- usuários com permissões distintas;
- nomes com acentos;
- dados incompletos permitidos;
- duplicidades prováveis;
- relógio controlado;
- valores monetários extremos e centavos;
- competência aberta e fechada.

## 12. Gates de release

Bloqueia release:

- vazamento entre clínicas;
- protocolo duplicado;
- divergência financeira;
- alteração de atendimento fechado;
- migration irreversível sem plano;
- vulnerabilidade crítica/alta;
- E2E crítico falhando;
- teste flaky ignorado;
- auditoria ausente em ação crítica.
