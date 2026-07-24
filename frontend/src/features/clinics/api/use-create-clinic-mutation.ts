import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createClinic } from './clinics-api'

export function useCreateClinicMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createClinic,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
