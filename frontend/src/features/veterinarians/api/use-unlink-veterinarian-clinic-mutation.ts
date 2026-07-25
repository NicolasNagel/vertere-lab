import { useMutation, useQueryClient } from '@tanstack/react-query'

import { unlinkVeterinarianClinic } from './veterinarians-api'

interface UnlinkVeterinarianClinicInput {
  veterinarianId: string
  clinicId: string
}

export function useUnlinkVeterinarianClinicMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ veterinarianId, clinicId }: UnlinkVeterinarianClinicInput) =>
      unlinkVeterinarianClinic(veterinarianId, clinicId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['veterinarians'] })
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
