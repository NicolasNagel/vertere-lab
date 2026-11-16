import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createVeterinarian, type VeterinarianFormValues } from './veterinarians-api'

interface CreateVeterinarianInput {
  values: VeterinarianFormValues
  clinicIds: string[]
  primaryClinicId?: string | null
}

export function useCreateVeterinarianMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ values, clinicIds, primaryClinicId }: CreateVeterinarianInput) =>
      createVeterinarian(values, clinicIds, primaryClinicId ?? null),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
