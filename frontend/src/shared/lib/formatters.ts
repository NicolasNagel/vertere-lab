/** Formatadores de exibição — nunca mudam o valor canônico armazenado
 * (rule: .claude/rules/05-frontend-web-mobile.md, "Máscara de exibição é separada do
 * valor canônico armazenado"). */

/** CNPJ chega do backend só com dígitos (`TaxId` normaliza para garantir
 * unicidade) — aqui só formatamos para leitura, não fazemos parsing. */
export function formatTaxId(value: string | null): string | null {
  if (!value) return value
  const digits = value.replace(/\D/g, '')
  if (digits.length !== 14) return value
  return digits.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5')
}

export function pluralize(count: number, singular: string, plural: string): string {
  return count === 1 ? singular : plural
}

const _currencyFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

/** API sends money as a decimal string (never a JSON number — rule:
 * .claude/rules/00-global.md, "dinheiro nunca é float"). This only formats
 * for display; the canonical value stays the string from the API. */
export function formatCurrencyBRL(value: string): string {
  return _currencyFormatter.format(Number(value))
}

/** Datas do backend chegam em UTC (`TIMESTAMPTZ`) — formatação usa o
 * timezone do navegador do usuário, nunca assume UTC na exibição (rule:
 * .claude/rules/05-frontend-web-mobile.md, "apresenta em pt-BR com o timezone
 * configurado").
 *
 * `isoDate` sem componente de hora (`service_date`, `billing_competence`:
 * `DATE`, não `TIMESTAMPTZ`) é uma data de calendário, não um instante — se
 * fosse interpretada como meia-noite UTC, um fuso atrás de UTC (ex.:
 * America/Sao_Paulo) exibiria o dia anterior. Nesse caso os componentes
 * y/m/d são lidos direto da string e a `Date` é construída no fuso local, em
 * vez de deixar `new Date(isoDate)` assumir UTC. */
export function formatDate(isoDate: string): string {
  const dateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate)
  const date = dateOnlyMatch
    ? new Date(Number(dateOnlyMatch[1]), Number(dateOnlyMatch[2]) - 1, Number(dateOnlyMatch[3]))
    : new Date(isoDate)
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' }).format(
    date,
  )
}

/** Same UTC-to-browser-timezone rule as `formatDate`, plus hour:minute. */
export function formatDateTime(isoDateTime: string): string {
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(isoDateTime))
}
