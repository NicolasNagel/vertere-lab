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

/** First letter of the first and last name segments, for avatar initials. */
export function getInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? (parts.at(-1)?.[0] ?? '') : ''
  return `${first}${last}`.toUpperCase()
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

/** Same UTC-to-browser-timezone rule as `formatDate`, plus hour:minute.
 * Date and time are formatted separately and joined with "·" — `Intl`'s
 * combined `dateStyle`/multi-field format uses a comma by default, which
 * doesn't match the design (`27/06 · 08:21`, never `27/06, 08:21`). */
export function formatDateTime(isoDateTime: string): string {
  const date = new Date(isoDateTime)
  const datePart = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' }).format(
    date,
  )
  const timePart = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(
    date,
  )
  return `${datePart} · ${timePart}`
}

/** `service_date` (`DATE`, no time component) paired with `created_at`
 * (`TIMESTAMPTZ`) to show a date+time pair the way the operation list does
 * (`DD/MM · HH:MM`) — falls back to `created_at` alone when there's no
 * `service_date` yet (draft) or it doesn't parse as a plain date. */
export function formatServiceDateTime(serviceDate: string | null, createdAt: string): string {
  if (!serviceDate) return formatDateTime(createdAt)
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(serviceDate)
  if (!match) return formatDateTime(createdAt)
  const createdTime = formatDateTime(createdAt).split(' · ')[1]
  return `${match[3]}/${match[2]} · ${createdTime ?? '—'}`
}
