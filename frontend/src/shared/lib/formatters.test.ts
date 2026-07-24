import { expect, test } from 'vitest'

import { formatTaxId, pluralize } from './formatters'

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
