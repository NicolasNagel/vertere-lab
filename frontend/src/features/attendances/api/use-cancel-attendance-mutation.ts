import { useMutation, useQueryClient } from '@tanstack/react-query'

import { cancelAttendance } from './attendances-api'

interface CancelAttendanceVariables {
  attendanceId: string
  reason: string
}

export function useCancelAttendanceMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ attendanceId, reason }: CancelAttendanceVariables) =>
      cancelAttendance(attendanceId, reason),
    onSuccess: (attendance) => {
      void queryClient.invalidateQueries({ queryKey: ['attendances'] })
      queryClient.setQueryData(['attendances', 'detail', attendance.id], attendance)
    },
  })
}
