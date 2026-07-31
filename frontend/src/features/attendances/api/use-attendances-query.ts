import { useQuery } from '@tanstack/react-query'

import { fetchAttendances, type AttendanceListParams } from './attendances-api'

export function attendancesQueryKey(params: AttendanceListParams) {
  return ['attendances', params] as const
}

export function useAttendancesQuery(params: AttendanceListParams | null) {
  return useQuery({
    queryKey: params ? attendancesQueryKey(params) : ['attendances', 'idle'],
    queryFn: () => fetchAttendances(params as AttendanceListParams),
    enabled: params !== null,
  })
}
