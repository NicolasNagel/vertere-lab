import { useMutation, useQueryClient } from '@tanstack/react-query'

import { importExams } from './catalog-api'

export function useImportExamsMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: importExams,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['exams'] })
    },
  })
}
