/** Dinheiro no cliente: texto decimal canônico ("1234.56") ou centavos em
 * `bigint` — nunca `Number`/float em soma ou em valor enviado à API (rule:
 * .claude/rules/00-global.md, "Dinheiro"). O total oficial continua vindo do
 * backend; isto só reapresenta valores que ele já calculou e normaliza o que o
 * usuário digita. */

const CANONICAL = /^(\d+)(?:\.(\d{1,2}))?$/

/** "100", "100.5" e "100.50" (formato canônico da API) -> centavos. */
export function toCents(value: string): bigint {
  const match = CANONICAL.exec(value.trim())
  if (!match) throw new RangeError(`Valor monetário inválido: "${value}"`)
  const [, whole = '0', fraction = ''] = match
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))
}

export function fromCents(cents: bigint): string {
  const sign = cents < 0n ? '-' : ''
  const abs = cents < 0n ? -cents : cents
  return `${sign}${abs / 100n}.${String(abs % 100n).padStart(2, '0')}`
}

export function sumMoney(values: readonly string[]): string {
  return fromCents(values.reduce((total, value) => total + toCents(value), 0n))
}

/** Interpreta o que o usuário digita em pt-BR ("1.234,56", "1234,5", "R$ 40")
 * e também o formato canônico ("1234.56"). Devolve o texto canônico com 2
 * casas, ou `null` quando não é um valor positivo com até 2 casas decimais.
 *
 * Um único "." seguido de exatamente 3 dígitos ("1.234") é separador de milhar
 * (pt-BR) e vira 1234.00, nunca 1.23. */
export function parseMoneyInput(input: string): string | null {
  const text = input.replace(/R\$|\s/g, '')
  if (!/^[\d.,]+$/.test(text)) return null

  const lastComma = text.lastIndexOf(',')
  const lastDot = text.lastIndexOf('.')
  let whole: string
  let fraction = ''
  if (lastComma >= 0) {
    // A vírgula é o decimal; qualquer "." antes dela é milhar.
    whole = text.slice(0, lastComma)
    fraction = text.slice(lastComma + 1)
    if (whole.includes(',') || !/^(\d{1,3}(\.\d{3})+|\d+)$/.test(whole)) return null
  } else if (lastDot >= 0) {
    const afterDot = text.slice(lastDot + 1)
    const isThousands = text.indexOf('.') !== lastDot || afterDot.length === 3
    if (isThousands) {
      if (!/^\d{1,3}(\.\d{3})+$/.test(text)) return null
      whole = text
    } else {
      whole = text.slice(0, lastDot)
      fraction = afterDot
    }
  } else {
    whole = text
  }

  if (!/^\d*$/.test(fraction) || fraction.length > 2) return null
  const digits = whole.replaceAll('.', '')
  if (digits === '') return null
  const canonical = `${digits}.${fraction.padEnd(2, '0')}`
  return toCents(canonical) > 0n ? fromCents(toCents(canonical)) : null
}
