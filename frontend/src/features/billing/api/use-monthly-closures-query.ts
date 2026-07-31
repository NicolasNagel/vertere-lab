import { useQuery } from '@tanstack/react-query'

import { fetchMonthlyClosures, type MonthlyClosureListParams } from './closures-api'

export function monthlyClosuresQueryKey(params: MonthlyClosureListParams) {
  return ['monthly-closures', params] as const
}

export function useMonthlyClosuresQuery(params: MonthlyClosureListParams | null) {
  return useQuery({
    queryKey: params ? monthlyClosuresQueryKey(params) : ['monthly-closures', 'idle'],
    queryFn: () => fetchMonthlyClosures(params as MonthlyClosureListParams),
    enabled: params !== null,
  })
}
