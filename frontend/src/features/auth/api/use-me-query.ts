import { useQuery } from '@tanstack/react-query'

import { fetchMe } from './auth-api'

export const meQueryKey = ['auth', 'me'] as const

export function useMeQuery() {
  return useQuery({
    queryKey: meQueryKey,
    queryFn: fetchMe,
    retry: false,
  })
}
