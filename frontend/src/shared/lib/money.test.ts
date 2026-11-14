import { expect, test } from 'vitest'

import { fromCents, parseMoneyInput, sumMoney, toCents } from './money'

test('sums decimal strings exactly and parses pt-BR and canonical input', () => {
  // 0.1 + 0.2 em float dá 0.30000000000000004.
  expect(sumMoney(['0.10', '0.20'])).toBe('0.30')
  expect(sumMoney(['100', '30.5', '0.05'])).toBe('130.55')
  expect(sumMoney([])).toBe('0.00')
  expect(toCents('1234.56')).toBe(123456n)
  expect(fromCents(-5n)).toBe('-0.05')
  expect(() => toCents('abc')).toThrow(RangeError)

  const accepted: Record<string, string> = {
    '1.234,56': '1234.56',
    '1234,5': '1234.50',
    '1234.56': '1234.56',
    '40': '40.00',
    '0,50': '0.50',
    'R$ 1.000': '1000.00',
    '12.345.678,90': '12345678.90',
  }
  for (const [input, expected] of Object.entries(accepted)) {
    expect(parseMoneyInput(input), input).toBe(expected)
  }
  for (const input of ['', '0', '0,00', 'abc', '1,234.56', '1,234,56', '12,345', '1.2.3', ',50']) {
    expect(parseMoneyInput(input), input).toBeNull()
  }
})
