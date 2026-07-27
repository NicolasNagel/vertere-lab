import { useMutation, useQueryClient } from '@tanstack/react-query'

import { assignUserRole } from './users-api'

interface AssignRoleInput {
  id: string
  roleId: string
}

export function useAssignRoleMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, roleId }: AssignRoleInput) => assignUserRole(id, roleId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
}
