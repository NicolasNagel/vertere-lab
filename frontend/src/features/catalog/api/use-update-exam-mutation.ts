import { useMutation, useQueryClient } from '@tanstack/react-query'

import { updateExam, type ExamFormValues, type ExamStatus } from './catalog-api'

interface UpdateExamInput {
  id: string
  values: ExamFormValues & { status: ExamStatus; expectedRowVersion: number }
}

export function useUpdateExamMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, values }: UpdateExamInput) => updateExam(id, values),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['exams'] })
    },
  })
}
