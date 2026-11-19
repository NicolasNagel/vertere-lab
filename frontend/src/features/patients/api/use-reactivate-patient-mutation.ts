import { useMutation, useQueryClient } from '@tanstack/react-query'

import { reactivatePatient } from './patients-api'

export function useReactivatePatientMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: reactivatePatient,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['patients'] })
    },
  })
}
