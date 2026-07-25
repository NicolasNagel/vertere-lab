import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createExamCategory } from './catalog-api'

export function useCreateExamCategoryMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createExamCategory,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['exam-categories'] })
    },
  })
}
