/** Formatadores de exibição — nunca mudam o valor canônico armazenado
 * (rule: .claude/rules/frontend.md, "Máscara de exibição é separada do
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
 * .claude/rules/globals.md, "dinheiro nunca é float"). This only formats
 * for display; the canonical value stays the string from the API. */
export function formatCurrencyBRL(value: string): string {
  return _currencyFormatter.format(Number(value))
}

/** Datas do backend chegam em UTC (`TIMESTAMPTZ`) — formatação usa o
 * timezone do navegador do usuário, nunca assume UTC na exibição (rule:
 * .claude/rules/frontend.md, "apresenta em pt-BR com o timezone
 * configurado"). */
export function formatDate(isoDate: string): string {
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' }).format(
    new Date(isoDate),
  )
}
