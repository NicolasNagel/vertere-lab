import { expect, test } from 'vitest'

import { formatDate, formatTaxId, pluralize } from './formatters'

test('formatTaxId masks 14 digits, is idempotent, leaves other values alone and passes through null', () => {
  expect(formatTaxId('21804204000155')).toBe('21.804.204/0001-55')
  expect(formatTaxId('21.804.204/0001-55')).toBe('21.804.204/0001-55')
  expect(formatTaxId('123')).toBe('123')
  expect(formatTaxId(null)).toBeNull()
})

test('pluralize picks the form by count', () => {
  expect(pluralize(1, 'ativa', 'ativas')).toBe('ativa')
  expect(pluralize(0, 'ativa', 'ativas')).toBe('ativas')
  expect(pluralize(2, 'ativa', 'ativas')).toBe('ativas')
})

test('formatDate keeps a date-only string on its own calendar day and converts full timestamps', () => {
  // Regression: `new Date('2026-07-01')` parses as UTC midnight, which in a
  // timezone behind UTC (e.g. America/Sao_Paulo, the app's own timezone —
  // AGENTS.md) formats as "30 de jun." instead of "01 de jul.". This must
  // hold regardless of the machine timezone running the test.
  expect(formatDate('2026-07-01')).toContain('01')
  expect(formatDate('2026-07-01')).toContain('jul')
  expect(formatDate('2026-01-01')).not.toContain('dez')
  // Um timestamp completo é convertido para o fuso local (fora da correção acima).
  expect(formatDate('2026-07-01T12:00:00Z')).toContain('jul')
})
