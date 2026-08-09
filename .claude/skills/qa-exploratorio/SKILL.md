---
name: qa-exploratorio
description: >-
  Use depois de implementar uma feature/fatia (API e/ou tela) para testar de verdade contra o
  app rodando — não simular. Cobre bug funcional e os 13 itens de segurança do
  docs/06-estrategia-qa.md §10. Carregada pelo comando /testar-app; pode ser lida diretamente
  quando alguém pedir "testa isso de verdade" ou "roda um teste de segurança nisso".
---
# QA Exploratório — Backend e Frontend

## Por que isto existe
Pedir para o Claude "simular" um teste no navegador ou na API sem executar nada de verdade é a
causa direta de alucinação de resultado — ele descreve o que *deveria* acontecer, não o que
*aconteceu*. Esta skill existe para trocar simulação por execução real: subir o app, bater nos
endpoints de verdade, dirigir um navegador de verdade (ou declarar que não há tela para dirigir),
e reportar só o que foi observado — inclusive no banco, não só no corpo da resposta HTTP.

**Regra de ouro:** se um passo não pôde ser executado (serviço fora do ar, Playwright não
instalado, falta de dado de teste, feature ainda sem tela), declare isso explicitamente no
relatório. Nunca escreva "passou" para um teste que não rodou.

## 0. Suba o ambiente de verdade

Não existe `docker-compose` nem `seed/gerar_dados_sinteticos.py` neste repositório ainda — monte
o ambiente manualmente, assim:

1. **Postgres descartável, não o testcontainers dos testes automatizados** (aquele sobe e morre
   por teste; aqui você precisa de um banco que sobrevive entre as chamadas manuais):
   ```
   docker run -d --name vertere-qa-pg -e POSTGRES_USER=vertere -e POSTGRES_PASSWORD=vertere \
     -e POSTGRES_DB=vertere -p 55432:5432 postgres:17-alpine
   ```
2. **Migrations** — não há `alembic.ini` no repo; configure programaticamente:
   ```
   DATABASE_URL="postgresql+psycopg://vertere:vertere@localhost:55432/vertere" \
     uv run python -c "
   from alembic.config import Config
   from alembic import command
   config = Config()
   config.set_main_option('script_location', 'alembic')
   command.upgrade(config, 'head')
   "
   ```
   Antes de aceitar isso como "migrado", cheque se há **múltiplas heads** (edição concorrente de
   outra sessão pode ter bifurcado a cadeia — já aconteceu): `alembic heads` deve devolver
   exatamente uma revisão. Mais de uma = pare e reconcilie antes de testar qualquer coisa.
3. **Backend**:
   ```
   DATABASE_URL="postgresql+psycopg://vertere:vertere@localhost:55432/vertere" \
     SESSION_COOKIE_SECURE=false ENV=dev LOG_LEVEL=WARNING \
     nohup uv run uvicorn --factory app.main:create_app --host 127.0.0.1 --port 8123 \
     > /tmp/scratch/uvicorn.log 2>&1 &
   ```
   Confirme com `curl -s http://127.0.0.1:8123/api/v1/health`. Se um `backend/.env` existir, uma
   variável de ambiente passada na linha de comando pode não vencer o arquivo dependendo de como
   `Settings` foi carregado — não assuma que o servidor conectou onde você mandou; confirme
   consultando o próprio banco (`\dt` via `docker exec ... psql`) depois da primeira chamada.

   No Windows/PowerShell, inicie o processo com `Start-Process -WindowStyle Hidden` e
   `-RedirectStandardOutput`/`-RedirectStandardError` apontando para arquivos distintos dentro de
   `$env:TEMP`. Guarde o PID retornado em uma variável da própria sessão. A captura não é
   opcional: ao final, concatene os dois arquivos e rode `scripts/pii_log_grep.py` sobre o log
   combinado. Sem arquivo capturado, a checagem de PII deve permanecer vermelha, nunca presumida.
4. **Usuários de teste reais** — não existe seed sintético ainda; use o bootstrap que já existe
   e crie os demais papéis manualmente na mesma sessão:
   ```
   DATABASE_URL="..." uv run python -m app.scripts.bootstrap_admin \
     --email admin@qa.local --full-name "QA Admin" --password "S3nhaForteQA!"
   ```
   Para papéis sem permissão (testar 403), insira direto via `UserModel`/`LabMembershipModel`
   reaproveitando o mesmo padrão de `app/scripts/bootstrap_admin.py` (criar `UserModel` com o
   `role_id` desejado + `LabMembershipModel` ativo).
5. **Frontend** (só se a feature tocar tela): `npm run dev` a partir de `frontend/`. **Se não
   existir rota/tela para a feature ainda** (comum quando só a fatia de backend foi entregue),
   não force Playwright contra nada — declare isso explicitamente na Parte 1 e siga só com o
   backend. Abrir o Swagger (`/docs`) no navegador para clicar em "Try it out" não é teste de
   tela de produto; é só mais uma forma de bater na API — não conta como "frontend testado".

Se qualquer pré-requisito não puder ser atendido nesta sessão, diga isso e rode só a parte
possível — não pule silenciosamente para "parece que está tudo certo".

## Parte 1 — Funcional (bug hunting)

### Backend (API real, via `httpx`, não teste unitário)
- Caminho feliz da feature nova, com dado real (a planilha/arquivo real do domínio quando a
  feature for de import/parsing — dado sintético minúsculo esconde bug de dado real).
- Valor de borda: campo vazio, string enorme, número negativo onde não devia, unicode/acento,
  payload com campo a mais (mass assignment).
- Repetir a mesma chamada (idempotência) quando o endpoint for de criação/confirmação/import.
- Estado inválido: tentar a ação num recurso no estado errado (ex.: confirmar atendimento já
  cancelado, reprocessar um lote com `batch_id` inexistente/malformado — confirme que um ID que
  não existe dá uma resposta que não confunde "nada a fazer" com "não deu erro nenhum").
- **Concorrência real, não só teórica**: `scripts/concurrency_probe.py` dispara N chamadas quase
  simultâneas no mesmo recurso com `asyncio.gather` (nunca sequencial fingindo concorrência)
  sempre que o fluxo criar/gravar algo a partir de um lote. **Um payload de 1 linha pode não abrir
  a janela de corrida** — se a primeira tentativa não reproduzir nada suspeito, repita com
  `--json-file` apontando pra uma carga maior (dezenas de linhas) antes de concluir que está
  seguro; foi exatamente escalando de 1 para 60 linhas + 8 chamadas concorrentes que uma
  duplicação real apareceu depois de uma tentativa menor não mostrar nada.
- **Confira o banco depois, não só a resposta HTTP.** A resposta de uma chamada concorrente pode
  parecer correta (`200`, contagem plausível) enquanto o banco tem linhas duplicadas que nenhuma
  resposta individual revela. Depois de qualquer teste de escrita/concorrência, rode a consulta
  direta: `docker exec <container> psql -U <user> -d <db> -c "SELECT COUNT(*), COUNT(DISTINCT
  <coluna-chave>) FROM <tabela> WHERE ..."` — as duas contagens devem bater (`concurrency_probe.py`
  já imprime esse lembrete no fim, mas não roda a query por você — o nome da tabela/coluna muda
  por feature).
- **Exaustão de recursos em endpoint de upload/parsing** (zip bomb / decompression bomb /
  amplificação de payload): `scripts/build_zip_bomb.py --output bomb.xlsx --target-mb 250` gera um
  arquivo pequeno construído para descomprimir/expandir muito (ex.: `.xlsx`/`.zip` com uma
  `sharedStrings.xml` de string repetida — poucos KB comprimidos podem virar centenas de MB). Um
  limite de tamanho só no upload comprimido não impede isso; suba o arquivo gerado no endpoint
  real e confirme que existe guarda sobre o tamanho *descomprimido/expandido* antes de qualquer
  parsing pesado — meça o tempo de resposta, um request que trava o processo por segundos com um
  arquivo pequeno é achado, mesmo que eventualmente responda.

### Frontend (Playwright real, não descrição do que a tela "deveria" fazer)
- Navegar até a tela nova e completar o fluxo principal.
- Testar os 5 estados obrigatórios (`05-frontend-web-mobile.md`): loading, erro, vazio, sucesso,
  desabilitado — force cada um (rede lenta/offline, resposta de erro, lista vazia).
- Navegação só por teclado até completar a ação principal.
- Duplo clique/duplo submit no botão de confirmação — não pode duplicar o efeito (mesma lógica
  do teste de concorrência de backend, aqui pelo clique real).
- Redimensionar para viewport mobile e checar quebra visual óbvia.
- Rolar a página/lista/tabela até o fim (não só olhar o topo) e checar se aparece faixa em branco
  ou com cor de fundo diferente da tela — sintoma de container com altura fixa (`height: 100vh`)
  sem contenção adequada do conteúdo interno.
- Testar toda tabela/lista com pelo menos um valor de campo anormalmente longo (código, nome,
  e-mail, nome de clínica) para checar se colunas vizinhas se sobrepõem — grid/flex sem
  `minmax(0, …)`/`min-width: 0` deixa o texto vazar sobre a coluna seguinte em vez de truncar.
- Ler o console do navegador — erro/warning novo é achado, mesmo que a tela "pareça" funcionar.

## Parte 2 — Segurança (docs/06-estrategia-qa.md §10 — 13 itens, testar todos que se aplicam)

| # | Item | Como testar de verdade |
|---|---|---|
| 1 | IDOR/BOLA | `scripts/probe_idor.py` — sessão (login real, cookie) de um usuário da clínica B acessando ID criado pela clínica A |
| 2 | Escalação horizontal | Usuário de um papel tentando ação de outro usuário do mesmo nível |
| 3 | Escalação vertical | Papel sem a permissão do endpoint (ex. `TECHNICAL`/`RECEPTION`) chamando endpoint de `FINANCE`/`LAB_ADMIN` — teste **todos** os endpoints tocados, não uma amostra |
| 4 | Brute force | `scripts/brute_force_probe.py --email <usuário de teste> --attempts 20` — deve haver rate limit/bloqueio antes de esgotar as tentativas |
| 5 | Enumeração de usuário | Comparar resposta de "e-mail existe" vs "e-mail não existe" no login/recuperação |
| 6 | CSRF | Conforme a estratégia de cookie adotada — requisição sem token/origem válida |
| 7 | XSS | `scripts/xss_payloads.txt` em todo campo de texto que é renderizado depois (nome, observação). Sem tela ainda? Teste que o payload é armazenado **literal** (não quebra parsing/serialização no backend) e documente a validação de renderização como pendente para quando a tela existir — não é "não aplicável", é "não testável ainda" |
| 8 | SQL injection | Payload de injeção em campo de busca/filtro/nome — nunca deve gerar erro 500 nem retornar dado fora do escopo; confirme a tabela/registro alvo continua íntegro depois |
| 9 | Mass assignment | `scripts/mass_assignment_probe.py --json '<payload legítimo>' --extra-field role=SUPER_ADMIN` — confirma que o campo extra é rejeitado ou ignorado, nunca refletido |
| 10 | Excesso de campos em response | Comparar o JSON de resposta com o schema documentado — campo interno vazando é achado |
| 11 | PII em log | `scripts/pii_log_grep.py --log-file /tmp/scratch/uvicorn.log` — varre CPF/CNPJ/e-mail/telefone/senha/token/cookie/connection-string em claro |
| 12 | Sessão após inativação | Inativar o usuário de teste e confirmar que a sessão existente para de funcionar |
| 13 | Exaustão de recursos (upload/parsing) | Ver item de concorrência/zip-bomb da Parte 1 — listado aqui de novo porque é achado de segurança (DoS), não só funcional |

Rode `scripts/security_header_check.py` sempre que a mudança tocar um endpoint novo — cobre
cabeçalhos de segurança básicos (não é um dos 13 itens da tabela, é checagem adicional barata).

## Matriz de permissão mínima (docs/06-estrategia-qa.md §4)
Para cada endpoint tocado, teste: sem sessão · sessão expirada · usuário inativo · papel sem
permissão · permissão correta em clínica errada · permissão correta no escopo correto ·
administrador do laboratório · alteração de papel durante a sessão. Teste **cada endpoint novo
individualmente** — não extrapole de um endpoint testado para os demais do mesmo módulo; a
autorização é checada por endpoint, e ausência de checagem num único endpoint já é achado.

## Encerramento do ambiente (sempre, mesmo em achado bloqueante)
Antes de fechar a sessão de QA:
1. Encerre o processo do backend (Windows/git-bash: `netstat -ano | grep LISTENING` para achar o
   PID na porta usada, depois `taskkill //PID <pid> //F` — `pkill`/`fuser` não existem neste
   ambiente).
2. `docker stop <container> && docker rm <container>` no Postgres descartável.
3. Apague scripts e arquivos temporários criados para o teste (payloads, arquivos de zip bomb).
Não deixe processo/container/arquivo de teste vivo entre sessões — o próximo QA não deve herdar
estado de um anterior.

## Como reportar
Separe **bug funcional** de **vulnerabilidade de segurança** — são categorias diferentes com
severidade diferente. Para cada achado: o que foi testado, o comando/script exato usado
(reprodutível por qualquer pessoa), o resultado observado (incluindo a consulta ao banco quando
aplicável), a severidade, e se bloqueia release conforme `docs/06-estrategia-qa.md §12`. Achado
sem reprodução exata não é achado, é suspeita — marque como suspeita e diga o que faltou pra
confirmar. Se corrigiu o achado na mesma sessão, reexecute o mesmo comando/script depois da
correção e reporte o resultado "antes vs. depois", não só "corrigido".
