import { useMutation, useQueryClient } from '@tanstack/react-query'

import { updateRole, type UpdateRoleValues } from './roles-api'

interface UpdateRoleInput {
  id: string
  values: UpdateRoleValues
}

export function useUpdateRoleMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, values }: UpdateRoleInput) => updateRole(id, values),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['roles'] })
    },
  })
}
