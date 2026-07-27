import { useMutation, useQueryClient } from '@tanstack/react-query'

import { activateUser } from './users-api'

export function useActivateUserMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: activateUser,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}
