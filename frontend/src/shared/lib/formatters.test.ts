import { expect, test } from 'vitest'

import { formatDate, formatTaxId, pluralize } from './formatters'

test('formats a 14-digit CNPJ into the standard mask', () => {
  expect(formatTaxId('21804204000155')).toBe('21.804.204/0001-55')
})

test('leaves an already-punctuated value untouched (idempotent)', () => {
  expect(formatTaxId('21.804.204/0001-55')).toBe('21.804.204/0001-55')
})

test('returns the original value unchanged when it does not have 14 digits', () => {
  expect(formatTaxId('123')).toBe('123')
})

test('passes through null', () => {
  expect(formatTaxId(null)).toBeNull()
})

test('pluralizes based on count', () => {
  expect(pluralize(1, 'ativa', 'ativas')).toBe('ativa')
  expect(pluralize(0, 'ativa', 'ativas')).toBe('ativas')
  expect(pluralize(2, 'ativa', 'ativas')).toBe('ativas')
})

test('formats a date-only string as its own calendar day, never shifted by UTC parsing', () => {
  // Regression: `new Date('2026-07-01')` parses as UTC midnight, which in a
  // timezone behind UTC (e.g. America/Sao_Paulo, the app's own timezone —
  // AGENTS.md) formats as "30 de jun." instead of "01 de jul.". This must
  // hold regardless of the machine timezone running the test.
  expect(formatDate('2026-07-01')).toContain('01')
  expect(formatDate('2026-07-01')).toContain('jul')
  expect(formatDate('2026-01-01')).not.toContain('dez')
})

test('formats a full timestamp by converting to the local timezone (unaffected by the date-only fix)', () => {
  expect(formatDate('2026-07-01T12:00:00Z')).toContain('jul')
})
