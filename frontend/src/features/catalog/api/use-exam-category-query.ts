import { useQuery } from '@tanstack/react-query'

import { fetchExamCategory } from './catalog-api'

export function useExamCategoryQuery(id: string | null) {
  return useQuery({
    queryKey: ['exam-categories', 'detail', id ?? ''] as const,
    queryFn: () => fetchExamCategory(id as string),
    enabled: id !== null,
  })
}
