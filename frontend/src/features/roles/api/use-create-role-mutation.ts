import { useMutation, useQueryClient } from '@tanstack/react-query'

import { createRole } from './roles-api'

export function useCreateRoleMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createRole,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['roles'] })
    },
  })
}
