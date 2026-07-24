import { useMutation, useQueryClient } from '@tanstack/react-query'

import { updateClinic, type ClinicFormValues, type ClinicStatus } from './clinics-api'

interface UpdateClinicInput {
  id: string
  values: ClinicFormValues & { status: ClinicStatus; expectedRowVersion: number }
}

export function useUpdateClinicMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, values }: UpdateClinicInput) => updateClinic(id, values),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['clinics'] })
    },
  })
}
