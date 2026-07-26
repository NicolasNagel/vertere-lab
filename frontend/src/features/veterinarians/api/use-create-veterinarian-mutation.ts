import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createVeterinarian, type VeterinarianFormValues } from './veterinarians-api'

interface CreateVeterinarianInput {
  values: VeterinarianFormValues
  clinicIds: string[]
}

export function useCreateVeterinarianMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ values, clinicIds }: CreateVeterinarianInput) =>
      createVeterinarian(values, clinicIds),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
