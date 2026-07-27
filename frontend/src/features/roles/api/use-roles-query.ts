import { useQuery } from '@tanstack/react-query'

import { fetchRoles, type RoleListParams } from './roles-api'

export function rolesQueryKey(params: RoleListParams) {
  return ['roles', params] as const
}

export function useRolesQuery(params: RoleListParams = {}) {
  return useQuery({
    queryKey: rolesQueryKey(params),
    queryFn: () => fetchRoles(params),
  })
}
