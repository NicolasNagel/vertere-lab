import { useQuery } from '@tanstack/react-query'

import { previewAttendance, type AttendanceConfirmItemInput } from './attendances-api'

/** Caller is expected to debounce `items` before passing them in — this
 * hook just reflects whatever it's given as a query key
 * (`.claude/rules/05-frontend-web-mobile.md`: "debounce em busca sem atrasar a
 * seleção"). `null` items (attendance not DRAFT, or nothing selected yet)
 * disables the query — a preview needs at least one item anyway. */
export function useAttendancePreviewQuery(
  attendanceId: string | null,
  items: AttendanceConfirmItemInput[] | null,
) {
  const key = items ? JSON.stringify(items) : 'idle'
  return useQuery({
    queryKey: ['attendances', 'preview', attendanceId, key] as const,
    queryFn: () => previewAttendance(attendanceId as string, items as AttendanceConfirmItemInput[]),
    enabled: attendanceId !== null && items !== null && items.length > 0,
  })
}
