import { useQuery } from '@tanstack/react-query'

import { fetchExams, type ExamListParams } from './catalog-api'

export function examsQueryKey(params: ExamListParams) {
  return ['exams', params] as const
}

export function useExamsQuery(params: ExamListParams | null = {}) {
  return useQuery({
    queryKey: params ? examsQueryKey(params) : ['exams', 'idle'],
    queryFn: () => fetchExams(params as ExamListParams),
    enabled: params !== null,
  })
}
