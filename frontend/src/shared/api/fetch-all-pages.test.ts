import { expect, test, vi } from 'vitest'

import { fetchAllPages } from './fetch-all-pages'

test('fetches every page without truncating selectors at 100 records', async () => {
  const fetchPage = vi.fn(async ({ page = 1, pageSize = 20 }) => {
    const allItems = Array.from({ length: 205 }, (_, index) => index + 1)
    const start = (page - 1) * pageSize
    return {
      items: allItems.slice(start, start + pageSize),
      total: allItems.length,
      page,
      pageSize,
    }
  })

  const result = await fetchAllPages(fetchPage, {})

  expect(result.items).toHaveLength(205)
  expect(result.items.at(-1)).toBe(205)
  expect(fetchPage).toHaveBeenCalledTimes(3)
  expect(fetchPage).toHaveBeenNthCalledWith(1, { page: 1, pageSize: 100 })
  expect(fetchPage).toHaveBeenNthCalledWith(3, { page: 3, pageSize: 100 })
})

test('stops safely if an inconsistent API returns an empty page before total', async () => {
  const fetchPage = vi.fn().mockResolvedValue({
    items: [],
    total: 10,
    page: 1,
    pageSize: 100,
  })

  await expect(fetchAllPages(fetchPage, {})).resolves.toMatchObject({ items: [], total: 10 })
  expect(fetchPage).toHaveBeenCalledOnce()
})
