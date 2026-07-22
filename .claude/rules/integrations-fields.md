---
# Regras de integrações/arquivos/laudos — carrega ao tocar reports, communications ou storage.
paths:
  - "backend/app/modules/reports/**"
  - "backend/app/modules/communications/**"
  - "backend/app/shared/infrastructure/storage/**"
---
# Regras de Integrações, Arquivos e Laudos
> Estes módulos são P1 (docs/02-prd.md §4) — a regra existe desde já para que, quando forem
> implementados, não repitam o problema de acoplamento e falta de auditoria da planilha atual.

## Integrações externas
- Um adapter por fornecedor; timeout explícito; retry só em erro transitório (nunca em erro de
  validação, por exemplo).
- Idempotência obrigatória; circuit breaker quando o volume justificar.
- Segredo fora do código; payload versionado; log sem PII.
- Webhook recebido exige assinatura, timestamp e proteção contra replay.
- **Integração nunca participa da transação principal** — chamada externa dentro de uma
  transação de negócio é proibida pelo `CLAUDE.md`.

## Arquivos
- Object storage privado; o banco guarda metadado e chave opaca, nunca o arquivo em si.
- Autorização checada **antes** de gerar URL assinada; URL de vida curta.
- Upload direto ao storage quando o arquivo exceder o limite seguro da Function (Vercel).
- Valide MIME, extensão, tamanho e hash — nome original do arquivo nunca é mecanismo de segurança.
- Arquivo local não é armazenamento durável em nenhuma circunstância nesta stack.
- Política de retenção definida por categoria de arquivo.

## Laudos (quando implementados)
- `AttendanceRecord` é a origem — laudo referencia o atendimento por ID, nunca duplica seus dados.
- Laudo publicado é **imutável**; correção gera nova versão, não edição do publicado.
- PDF gerado por worker externo quando o processamento for pesado ou durável (não dentro de uma
  Vercel Function stateless).
- Hash do arquivo gerado; autoria e revisão registradas; download é auditado.
- Envio ocorre via outbox/job — nunca dentro da transação que publica o laudo.