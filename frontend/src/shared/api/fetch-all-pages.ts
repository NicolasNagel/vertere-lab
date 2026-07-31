export interface PageRequest {
  page?: number
  pageSize?: number
}

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

const MAX_API_PAGE_SIZE = 100

export async function fetchAllPages<T, P extends PageRequest>(
  fetchPage: (params: P) => Promise<PageResult<T>>,
  params: P,
): Promise<PageResult<T>> {
  const items: T[] = []
  let page = 1
  let total = 0

  do {
    const result = await fetchPage({ ...params, page, pageSize: MAX_API_PAGE_SIZE })
    items.push(...result.items)
    total = result.total

    if (result.items.length === 0) {
      break
    }
    page += 1
  } while (items.length < total)

  return { items, total, page: 1, pageSize: items.length }
}
