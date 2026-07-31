import { useQuery } from '@tanstack/react-query'

import { fetchAttendanceTimeline } from './attendances-api'

const PAGE_SIZE = 20

/** Only fetches once the timeline section is expanded (`enabled` from the
 * caller) — a paginated audit trail nobody asked to see yet is exactly the
 * "waterfall de requisição desnecessário" `.claude/rules/05-frontend-web-mobile.md`
 * says to avoid. */
export function useAttendanceTimelineQuery(attendanceId: string, page: number, enabled: boolean) {
  return useQuery({
    queryKey: ['attendances', 'timeline', attendanceId, page] as const,
    queryFn: () => fetchAttendanceTimeline(attendanceId, page, PAGE_SIZE),
    enabled,
  })
}
