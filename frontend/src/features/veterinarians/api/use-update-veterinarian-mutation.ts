import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  updateVeterinarian,
  type VeterinarianFormValues,
  type VeterinarianStatus,
} from './veterinarians-api'

interface UpdateVeterinarianInput {
  id: string
  values: VeterinarianFormValues & {
    status: VeterinarianStatus
    expectedRowVersion: number
    reason: string
  }
}

export function useUpdateVeterinarianMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, values }: UpdateVeterinarianInput) => updateVeterinarian(id, values),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
    },
  })
}
