import { expect, test } from 'vitest'

import { groupItemsByCategory } from './group-by-category'

test('sums and counts per category and buckets a null category (pre-migration snapshot) as Outros', () => {
  expect(
    groupItemsByCategory([
      { examCategory: 'Hematológico', totalAmount: '75.00' },
      { examCategory: 'Hematológico', totalAmount: '480.00' },
      { examCategory: 'Bioquímico', totalAmount: '120.00' },
    ]),
  ).toEqual([
    { category: 'Hematológico', count: 2, total: '555.00' },
    { category: 'Bioquímico', count: 1, total: '120.00' },
  ])

  expect(groupItemsByCategory([{ examCategory: null, totalAmount: '50.00' }])).toEqual([
    { category: 'Outros', count: 1, total: '50.00' },
  ])

  expect(
    groupItemsByCategory([
      { examCategory: 'A', totalAmount: '0.10' },
      { examCategory: 'A', totalAmount: '0.20' },
    ])[0]?.total,
  ).toBe('0.30')
})
