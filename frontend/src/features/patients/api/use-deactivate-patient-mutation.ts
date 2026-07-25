import { useMutation, useQueryClient } from '@tanstack/react-query'

import { deactivatePatient } from './patients-api'

export function useDeactivatePatientMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deactivatePatient,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['patients'] })
    },
  })
}
