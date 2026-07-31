import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createAttendanceDraft } from './attendances-api'

export function useCreateAttendanceDraftMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createAttendanceDraft,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['attendances'] })
    },
  })
}
