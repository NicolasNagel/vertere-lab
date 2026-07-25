import { useMutation, useQueryClient } from '@tanstack/react-query'

import { deactivateExam } from './catalog-api'

export function useDeactivateExamMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deactivateExam,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['exams'] })
    },
  })
}
