# Pendências — redesign de Operação e pacotes de exames

Lista viva, anotada durante as fatias; corrigir tudo em um laço ao final.
Formato: `[ ]` aberto · `[x]` resolvido.

## Catálogo / pacotes
- [ ] Pacote não tem quantidade por componente: TRANSFUSÃO 1/2 do papel pedem hemograma
      doador + receptor e 3 hematócritos seriados; no catálogo de teste entram 1× cada.
- [ ] `GET /exams` limita `pageSize` a 50: a grade de exames da tela de protocolo precisa
      buscar por categoria/paginar (ou endpoint próprio de catálogo agrupado).
- [ ] Downgrade da migration 0039 não foi executado (só upgrade); testar rollback.
- [ ] Script de seed do catálogo de teste mora só no scratchpad; decidir se vira
      `backend/scripts/seed_dev_catalog.py` (preços são fictícios).
- [ ] Telas de Exames & Preços ainda no visual antigo (não ERP); o formulário de pacote herda isso.
- [ ] QA de tablet/celular do formulário de pacote não foi feito.

## Protocolo (a fazer nas próximas fatias)
- [ ] Aviso (não bloqueio) quando um exame avulso já faz parte de um pacote do carrinho.
- [ ] Hora da coleta: decidido NÃO implementar.
- [ ] Campo "Histórico/Observações" do papel: decidido não exibir (`notes` segue no backend).

- [ ] Painel "Valor" ainda tem o selo numérico "5" e visual antigo; refazer na fatia do resumo.
- [ ] Seções "Exames" e "Atendimento" da tela de protocolo ainda no visual antigo
      (a grade por categoria entra na fatia 5).
- [ ] Lista de exames aparece inteira antes de a clínica/paciente serem escolhidos (só desabilitada).
- [ ] Axe/e2e não cobre a tela de novo protocolo; rodar verificação de acessibilidade nela.
- [ ] Seta do dropdown de campo aparece "quebrada" quando aberto na captura imediata
      (provável transição de 120 ms; confirmar com espera).

## Transversais
- [ ] 401 no console do navegador durante roteiros de QA (não investigado).
- [ ] Teste de frontend intermitente já visto uma vez (passou em 3 reexecuções), não diagnosticado.
- [ ] Seta do dropdown de Clínica apareceu meio girada numa captura (provável animação); confirmar.
- [ ] Logs da plataforma Vercel podem conter query string (fora do filtro do uvicorn).
- [ ] QA exploratório completo de Veterinários, Pacientes, Exames, Usuários e Fechamento.
