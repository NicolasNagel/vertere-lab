import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createExam } from './catalog-api'

export function useCreateExamMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createExam,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['exams'] })
    },
  })
}
