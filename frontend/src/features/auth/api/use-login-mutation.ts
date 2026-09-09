import { useMutation, useQueryClient } from '@tanstack/react-query'

import { login } from './auth-api'
import { meQueryKey } from './use-me-query'

export function useLoginMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      // Remove stale server state from a previous actor without deleting the
      // active `auth/me` observer or the login mutation that is completing.
      // `clear()` disconnects both and leaves the browser on the login route.
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'auth' })
      queryClient.setQueryData(meQueryKey, user)
    },
  })
}
