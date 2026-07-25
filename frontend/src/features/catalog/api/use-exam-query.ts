import { useQuery } from '@tanstack/react-query'

import { fetchExam } from './catalog-api'

export function examQueryKey(id: string) {
  return ['exams', 'detail', id] as const
}

export function useExamQuery(id: string | null) {
  return useQuery({
    queryKey: examQueryKey(id ?? ''),
    queryFn: () => fetchExam(id as string),
    enabled: id !== null,
  })
}
