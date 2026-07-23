import { useMutation, useQueryClient } from '@tanstack/react-query'

import { login } from './auth-api'
import { meQueryKey } from './use-me-query'

export function useLoginMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      queryClient.setQueryData(meQueryKey, user)
    },
  })
}
