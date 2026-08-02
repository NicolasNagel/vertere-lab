import { useQuery } from '@tanstack/react-query'

import { fetchAttendanceStatusCounts, type AttendanceStatusCountsParams } from './attendances-api'

export function useAttendanceStatusCountsQuery(params: AttendanceStatusCountsParams | null) {
  return useQuery({
    queryKey: ['attendances', 'status-counts', params],
    queryFn: () => fetchAttendanceStatusCounts(params ?? {}),
    enabled: params !== null,
  })
}
