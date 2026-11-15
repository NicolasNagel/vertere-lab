import { useMutation, useQueryClient } from '@tanstack/react-query'

import { updateVeterinarianClinics, type VeterinarianClinicsChange } from './veterinarians-api'

interface UpdateVeterinarianClinicsInput {
  veterinarianId: string
  change: VeterinarianClinicsChange
}

export function useUpdateVeterinarianClinicsMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ veterinarianId, change }: UpdateVeterinarianClinicsInput) =>
      updateVeterinarianClinics(veterinarianId, change),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
