import { useMutation, useQueryClient } from '@tanstack/react-query'

import { updateAttendance, type AttendanceUpdateInput } from './attendances-api'

interface UpdateAttendanceVariables {
  attendanceId: string
  rowVersion: number
  input: AttendanceUpdateInput
}

export function useUpdateAttendanceMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ attendanceId, rowVersion, input }: UpdateAttendanceVariables) =>
      updateAttendance(attendanceId, rowVersion, input),
    onSuccess: (attendance) => {
      void queryClient.invalidateQueries({ queryKey: ['attendances'] })
      queryClient.setQueryData(['attendances', 'detail', attendance.id], attendance)
    },
  })
}
