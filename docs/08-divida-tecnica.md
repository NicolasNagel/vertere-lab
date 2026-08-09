# Registro de dívida técnica

Este registro separa limitações conscientemente aceitas de funcionalidades esquecidas. Nenhum
item abaixo autoriza contornar autorização, auditoria, snapshots ou integridade transacional.

## DT-001 — `Owner` embutido em `Patient`

**Estado atual:** nome e contato do tutor são colunas de `patients`; não existe agregado, tabela,
API ou tela independente de `Owner`. As permissões `owners.read` e `owners.manage` permanecem no
catálogo, mas não protegem nenhum caso de uso.

**Impacto:** o mesmo tutor pode ser duplicado entre pacientes e não há histórico ou merge próprio.

**Saída:** migration expand-first criando `owners`, reconciliação assistida, FK opcional em
`patients`, dupla leitura temporária e somente depois remoção das colunas antigas. Reavaliar as
permissões antes de ativá-las. Decisão original: ADR-004.

## DT-002 — preço vigente embutido em `Exam`

**Estado atual:** `price_base` e adicionais ficam diretamente no exame. Não existem
`PriceTable`/`PriceTableItem` nem vigência por clínica ou período.

**Impacto:** não é possível programar reajuste ou representar contratos comerciais distintos.
Atendimentos confirmados permanecem corretos porque conservam snapshots imutáveis.

**Saída:** tabelas aditivas de preço e vigência, backfill do preço atual como primeira versão e
resolução server-side por clínica/data. `Exam.price_base` permanece como fallback durante a
transição. Decisão original: ADR-005.

## DT-003 — códigos históricos de método de coleta

**Estado atual:** `CollectionMethod` contém códigos derivados de nomes de pessoas
(`HELITO_NICOLAS`, `MARLI`) por compatibilidade com a planilha.

**Impacto:** o contrato confunde responsável operacional com modalidade de coleta e dificulta
trocas de equipe.

**Saída:** definir códigos semânticos estáveis, mapear os códigos históricos como aliases e migrar
dados sem recalcular atendimentos ou apagar seus snapshots. A alteração exige ADR e compatibilidade
de leitura durante a transição.

## DT-004 — nome histórico `MonthlyClosure`

**Estado atual:** `MonthlyClosure` e `monthly_closures` representam fechamento por intervalo civil
livre e inclusivo (`period_start`/`period_end`), não necessariamente um mês. `competence_year` e
`competence_month` são metadados derivados.

**Impacto:** o nome pode induzir integrações novas a assumir mês calendário.

**Saída:** contratos novos sempre usam período explícito. Uma renomeação futura exige migration,
compatibilidade de API e plano para relatórios existentes. Decisão: ADR-010.

## DT-005 — endpoint depreciado de alteração de papel

**Estado atual:** `PATCH /api/v1/users/{id}/role` permanece disponível e marcado como depreciado.
Ele delega à mudança de acesso, enquanto clientes novos devem usar
`PATCH /api/v1/users/{id}/access` com `role_id`, `clinic_ids` e `expected_row_version`.

**Impacto:** clientes antigos podem não expressar memberships explicitamente e prolongam duas
superfícies públicas para a mesma ação.

**Saída:** medir uso, migrar o frontend e integrações restantes, anunciar versão de remoção e
retirar o endpoint somente após uma janela de compatibilidade. Mudanças continuam revogando
sessões e auditando o diff.

## DT-006 — jornada Playwright integral contra backend real

**Estado atual:** integração PostgreSQL cobre o núcleo e Playwright cobre navegador, responsividade
e axe, mas ainda não há um único teste que percorra toda a jornada contra o mesmo backend real.

**Impacto:** falhas de composição entre etapas podem ser detectadas apenas pelas suítes em camadas.

**Saída:** fixture descartável que sobe banco, migrations, backend e frontend; dados de duas
clínicas e papéis distintos; cenário único de cadastro, confirmação, fechamento, bloqueio,
ajuste e tentativa cross-tenant. Não substituir os testes unitários e de integração existentes.

## Priorização

| Item | Risco atual | Gatilho para execução |
|---|---|---|
| DT-001 | médio | necessidade de deduplicar tutor ou compartilhar contato |
| DT-002 | alto para evolução comercial | primeiro preço por vigência/clínica |
| DT-003 | médio | mudança operacional de equipe/coleta |
| DT-004 | baixo, compatibilidade | versão maior de domínio/API |
| DT-005 | médio | telemetria confirmar ausência de clientes antigos |
| DT-006 | alto para release | antes da liberação do núcleo em produção |
