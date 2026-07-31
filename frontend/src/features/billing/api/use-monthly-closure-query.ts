import { useQuery } from '@tanstack/react-query'

import { fetchMonthlyClosure } from './closures-api'

export function monthlyClosureQueryKey(id: string) {
  return ['monthly-closures', 'detail', id] as const
}

export function useMonthlyClosureQuery(id: string | null) {
  return useQuery({
    queryKey: id ? monthlyClosureQueryKey(id) : ['monthly-closures', 'detail', 'idle'],
    queryFn: () => fetchMonthlyClosure(id as string),
    enabled: id !== null,
  })
}
