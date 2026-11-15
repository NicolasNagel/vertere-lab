import { useMutation, useQueryClient } from '@tanstack/react-query'

import { linkVeterinarianClinic } from './veterinarians-api'

interface LinkVeterinarianClinicInput {
  veterinarianId: string
  clinicId: string
  reason: string
  primary?: boolean
}

export function useLinkVeterinarianClinicMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ veterinarianId, clinicId, reason, primary }: LinkVeterinarianClinicInput) =>
      linkVeterinarianClinic(veterinarianId, clinicId, reason, primary),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
