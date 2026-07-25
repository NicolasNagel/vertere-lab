import { useQuery } from '@tanstack/react-query'

import { fetchActiveExamCategories } from './catalog-api'

export function useActiveExamCategoriesQuery() {
  return useQuery({
    queryKey: ['exam-categories', 'active'] as const,
    queryFn: fetchActiveExamCategories,
  })
}
