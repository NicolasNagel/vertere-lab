import { useMutation, useQueryClient } from '@tanstack/react-query'

import { unlinkVeterinarianClinic } from './veterinarians-api'

interface UnlinkVeterinarianClinicInput {
  veterinarianId: string
  clinicId: string
  reason: string
}

export function useUnlinkVeterinarianClinicMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ veterinarianId, clinicId, reason }: UnlinkVeterinarianClinicInput) =>
      unlinkVeterinarianClinic(veterinarianId, clinicId, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
