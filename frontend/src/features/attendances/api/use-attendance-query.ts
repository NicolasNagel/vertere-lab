import { useQuery } from '@tanstack/react-query'

import { fetchAttendance } from './attendances-api'

export function attendanceQueryKey(id: string) {
  return ['attendances', 'detail', id] as const
}

export function useAttendanceQuery(id: string | null) {
  return useQuery({
    queryKey: id ? attendanceQueryKey(id) : ['attendances', 'detail', 'idle'],
    queryFn: () => fetchAttendance(id as string),
    enabled: id !== null,
  })
}
