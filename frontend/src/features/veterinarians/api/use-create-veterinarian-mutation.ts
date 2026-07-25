import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createVeterinarian } from './veterinarians-api'

export function useCreateVeterinarianMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createVeterinarian,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
    },
  })
}
