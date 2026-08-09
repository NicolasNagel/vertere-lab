import { useQuery } from '@tanstack/react-query'
import { useActorScopeKey } from '../../auth/use-actor-scope-key'

import { fetchAttendances, type AttendanceListParams } from './attendances-api'

export function attendancesQueryKey(params: AttendanceListParams, actorScope = 'unknown') {
  return ['attendances', actorScope, params] as const
}

export function useAttendancesQuery(params: AttendanceListParams | null) {
  const actorScope = useActorScopeKey()
  return useQuery({
    queryKey: params ? attendancesQueryKey(params, actorScope) : ['attendances', actorScope, 'idle'],
    queryFn: () => fetchAttendances(params as AttendanceListParams),
    enabled: params !== null,
  })
}
