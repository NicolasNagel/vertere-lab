import { useQuery } from '@tanstack/react-query'
import { useActorScopeKey } from '../../auth/use-actor-scope-key'

import { fetchMonthlyClosures, type MonthlyClosureListParams } from './closures-api'

export function monthlyClosuresQueryKey(params: MonthlyClosureListParams, actorScope = 'unknown') {
  return ['monthly-closures', actorScope, params] as const
}

export function useMonthlyClosuresQuery(params: MonthlyClosureListParams | null) {
  const actorScope = useActorScopeKey()
  return useQuery({
    queryKey: params
      ? monthlyClosuresQueryKey(params, actorScope)
      : ['monthly-closures', actorScope, 'idle'],
    queryFn: () => fetchMonthlyClosures(params as MonthlyClosureListParams),
    enabled: params !== null,
  })
}
