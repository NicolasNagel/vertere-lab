import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createPatient } from './patients-api'

export function useCreatePatientMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createPatient,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['patients'] })
    },
  })
}
