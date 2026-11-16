import { useMutation, useQueryClient } from '@tanstack/react-query'

import { updateAttendanceItems, type AttendanceItemEditInput } from './attendances-api'

interface UpdateAttendanceItemsVariables {
  attendanceId: string
  rowVersion: number
  reason: string
  items: AttendanceItemEditInput[]
}

export function useUpdateAttendanceItemsMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ attendanceId, rowVersion, reason, items }: UpdateAttendanceItemsVariables) =>
      updateAttendanceItems(attendanceId, rowVersion, reason, items),
    onSuccess: (attendance) => {
      void queryClient.invalidateQueries({ queryKey: ['attendances'] })
      queryClient.setQueryData(['attendances', 'detail', attendance.id], attendance)
    },
  })
}
