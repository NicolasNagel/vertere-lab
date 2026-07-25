import { useQuery } from '@tanstack/react-query'

import { fetchExams, type ExamListParams } from './catalog-api'

export function examsQueryKey(params: ExamListParams) {
  return ['exams', params] as const
}

export function useExamsQuery(params: ExamListParams = {}) {
  return useQuery({
    queryKey: examsQueryKey(params),
    queryFn: () => fetchExams(params),
  })
}
