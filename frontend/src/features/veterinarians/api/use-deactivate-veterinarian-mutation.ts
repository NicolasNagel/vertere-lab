import { useMutation, useQueryClient } from '@tanstack/react-query'

import { deactivateVeterinarian } from './veterinarians-api'

export function useDeactivateVeterinarianMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: deactivateVeterinarian,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
    },
  })
}
