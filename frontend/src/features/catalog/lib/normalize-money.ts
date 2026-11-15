/** "12,5" ou "12.50" vira "12.50"; qualquer outra coisa é inválida (null). */
export function normalizeMoney(value: string): string | null {
  const trimmed = value.trim().replace(',', '.')
  if (!/^\d{1,12}(\.\d{1,2})?$/.test(trimmed)) return null
  return Number(trimmed).toFixed(2)
}
