---
# Regras de observabilidade/perf/devops — carrega ao tocar config, logging, infra ou CI.
paths:
  - "backend/app/core/logging.py"
  - "backend/app/core/config.py"
  - "infra/**"
  - ".github/workflows/**"
---
# Regras de Observabilidade, Performance e DevOps

## Logs
JSON estruturado; `request_id` em toda requisição; usuário e clínica quando seguro fazê-lo (sem
PII crua); módulo, caso de uso, duração, status e código de erro. Sem PII desnecessária; stack
trace só em ambiente seguro (nunca na resposta ao cliente).

## Métricas
Latência e erro por endpoint · consulta lenta · conexão PostgreSQL ativa · falha de login ·
acesso negado · atendimento criado/cancelado · conflito de idempotência · fechamento
criado/reaberto · divergência detectada em reconciliação · fila (quando existir).

## Performance
Meça antes de otimizar. Lista sempre paginada; evite N+1 nos fluxos críticos; conheça o plano de
consulta do fluxo crítico (`EXPLAIN`); índice nasce de uso real, não de precaução; pooler
obrigatório em ambiente serverless; cache só com hipótese e métrica que confirme o ganho.

## Vercel
Frontend e backend podem ser projetos Vercel separados. Nenhuma dependência de disco persistente;
migration roda fora do startup da aplicação; nenhum worker persistente; controle payload e
duração de requisição; região do backend próxima ao banco; ambiente de preview nunca usa dado de
produção; variável de ambiente separada por estágio.

## CI/CD — pipeline mínima
1. Ruff check/format check;
2. mypy;
3. pytest unitário;
4. pytest integração com PostgreSQL real;
5. `alembic upgrade` em banco limpo;
6. frontend lint/typecheck/test;
7. build;
8. Playwright crítico em staging/preview;
9. secret scan + dependency scan;
10. deploy;
11. smoke test pós-deploy.
Nenhuma etapa é "opcional quando dá pressa" — se algo precisar ser pulado por urgência real, isso
é decisão registrada, não hábito silencioso.

## Migrations em produção
Nunca rodar automaticamente a cada cold start; etapa única e controlada; backup antes de mudança
arriscada; compatibilidade entre versão antiga e nova durante o rollout (deploy de app e de
schema não são simultâneos por padrão); plano de rollback de aplicação **e** de dado, os dois
documentados separadamente.