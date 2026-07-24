import { useMutation, useQueryClient } from '@tanstack/react-query'

import { deactivateClinic } from './clinics-api'

export function useDeactivateClinicMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deactivateClinic,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
