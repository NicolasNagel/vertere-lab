import { useQuery } from '@tanstack/react-query'

import { fetchMonthlyClosures, type MonthlyClosureListParams } from './closures-api'

export function monthlyClosuresQueryKey(params: MonthlyClosureListParams) {
  return ['monthly-closures', params] as const
}

export function useMonthlyClosuresQuery(params: MonthlyClosureListParams) {
  return useQuery({
    queryKey: monthlyClosuresQueryKey(params),
    queryFn: () => fetchMonthlyClosures(params),
  })
}
