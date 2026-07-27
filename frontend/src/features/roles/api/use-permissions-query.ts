import { useQuery } from '@tanstack/react-query'

import { fetchPermissions } from './roles-api'

export function permissionsQueryKey() {
  return ['permissions'] as const
}

export function usePermissionsQuery() {
  return useQuery({
    queryKey: permissionsQueryKey(),
    queryFn: fetchPermissions,
    staleTime: 5 * 60 * 1000,
  })
}
