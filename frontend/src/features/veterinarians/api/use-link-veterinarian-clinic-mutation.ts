import { useMutation, useQueryClient } from '@tanstack/react-query'

import { linkVeterinarianClinic } from './veterinarians-api'

interface LinkVeterinarianClinicInput {
  veterinarianId: string
  clinicId: string
  primary?: boolean
}

export function useLinkVeterinarianClinicMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ veterinarianId, clinicId, primary }: LinkVeterinarianClinicInput) =>
      linkVeterinarianClinic(veterinarianId, clinicId, primary),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
