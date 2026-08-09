import { describe, expect, test } from 'vitest'

import { groupItemsByCategory } from './group-by-category'

describe('groupItemsByCategory', () => {
  test('sums totals and counts items per category', () => {
    const groups = groupItemsByCategory([
      { examCategory: 'Hematológico', totalAmount: '75.00' },
      { examCategory: 'Hematológico', totalAmount: '480.00' },
      { examCategory: 'Bioquímico', totalAmount: '120.00' },
    ])

    expect(groups).toEqual([
      { category: 'Hematológico', count: 2, total: '555' },
      { category: 'Bioquímico', count: 1, total: '120' },
    ])
  })

  test('buckets a null category (pre-migration snapshot) as Outros', () => {
    const groups = groupItemsByCategory([{ examCategory: null, totalAmount: '50.00' }])

    expect(groups).toEqual([{ category: 'Outros', count: 1, total: '50' }])
  })
})
