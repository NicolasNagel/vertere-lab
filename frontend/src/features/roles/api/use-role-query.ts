import { useQuery } from '@tanstack/react-query'

import { fetchRole } from './roles-api'

export function roleQueryKey(id: string) {
  return ['roles', 'detail', id] as const
}

export function useRoleQuery(id: string | null) {
  return useQuery({
    queryKey: roleQueryKey(id ?? ''),
    queryFn: () => fetchRole(id as string),
    enabled: id !== null,
  })
}
