# Pendências — redesign de Operação e pacotes de exames

Lista viva, anotada durante as fatias; corrigir tudo em um laço ao final.
Formato: `[ ]` aberto · `[x]` resolvido.

## Catálogo / pacotes
- [ ] Pacote não tem quantidade por componente: TRANSFUSÃO 1/2 do papel pedem hemograma
      doador + receptor e 3 hematócritos seriados; no catálogo de teste entram 1× cada.
- [x] (era engano) `GET /exams` aceita `page_size` até 100; a grade carrega todas as páginas.
- [ ] Downgrade da migration 0039 não foi executado (só upgrade); testar rollback.
- [ ] Script de seed do catálogo de teste mora só no scratchpad; decidir se vira
      `backend/scripts/seed_dev_catalog.py` (preços são fictícios).
- [ ] Telas de Exames & Preços ainda no visual antigo (não ERP); o formulário de pacote herda isso.
- [ ] QA de tablet/celular do formulário de pacote não foi feito.

## Protocolo (a fazer nas próximas fatias)
- [ ] Aviso (não bloqueio) quando um exame avulso já faz parte de um pacote do carrinho.
- [ ] Hora da coleta: decidido NÃO implementar.
- [ ] Campo "Histórico/Observações" do papel: decidido não exibir (`notes` segue no backend).

- [x] Painel "Valor", "Atendimento" e grade de exames refeitos (fatia 5).
- [ ] Grade lista o catálogo inteiro antes de clínica/paciente (só desabilitada); decidir se esconde.
- [ ] Quantidade/desconto por item ficam na lista "Exames selecionados", no fim da página,
      longe da grade; avaliar subir para perto do resumo.
- [ ] Ordem das categorias é Perfis + alfabética; o papel usa Hematologia, Bioquímica,
      Hemogasometria, Urinálise, Coproparasitológicos (catálogo não tem campo de ordem).
- [ ] Pacote por checkbox ignora que o mesmo exame pode ser pedido em quantidade >1 só na lista inferior.
- [ ] Axe/e2e não cobre a tela de novo protocolo; rodar verificação de acessibilidade nela.
- [ ] Seta do dropdown de campo aparece "quebrada" quando aberto na captura imediata
      (provável transição de 120 ms; confirmar com espera).

## Transversais
- [x] 401 no console era a checagem anônima GET /auth/me da tela de login (esperado).
- [x] 422 de prévia após confirmar atendimento: corrigido (prévia não é refeita depois de confirmar).
- [ ] Teste de frontend intermitente já visto uma vez (passou em 3 reexecuções), não diagnosticado.
- [ ] Seta do dropdown de Clínica apareceu meio girada numa captura (provável animação); confirmar.
- [ ] Logs da plataforma Vercel podem conter query string (fora do filtro do uvicorn).
- [ ] QA exploratório completo de Veterinários, Pacientes, Exames, Usuários e Fechamento.
