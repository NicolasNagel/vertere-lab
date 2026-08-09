import { useQuery } from '@tanstack/react-query'
import { useActorScopeKey } from '../../auth/use-actor-scope-key'

import { fetchAttendanceStatusCounts, type AttendanceStatusCountsParams } from './attendances-api'

export function useAttendanceStatusCountsQuery(params: AttendanceStatusCountsParams | null) {
  const actorScope = useActorScopeKey()
  return useQuery({
    queryKey: ['attendances', actorScope, 'status-counts', params],
    queryFn: () => fetchAttendanceStatusCounts(params ?? {}),
    enabled: params !== null,
  })
}
