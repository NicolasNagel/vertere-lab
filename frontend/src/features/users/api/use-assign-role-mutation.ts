import { useMutation, useQueryClient } from '@tanstack/react-query'

import { updateUserAccess } from './users-api'

interface AssignRoleInput {
  id: string
  roleId: string
  clinicIds: string[]
  expectedRowVersion: number
}

export function useAssignRoleMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, roleId, clinicIds, expectedRowVersion }: AssignRoleInput) =>
      updateUserAccess(id, roleId, clinicIds, expectedRowVersion),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}
