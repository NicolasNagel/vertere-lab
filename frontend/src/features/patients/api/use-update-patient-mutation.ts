import { useMutation, useQueryClient } from '@tanstack/react-query'

import { updatePatient, type PatientUpdateValues } from './patients-api'

interface UpdatePatientInput {
  id: string
  values: PatientUpdateValues
}

export function useUpdatePatientMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, values }: UpdatePatientInput) => updatePatient(id, values),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['patients'] })
    },
  })
}
