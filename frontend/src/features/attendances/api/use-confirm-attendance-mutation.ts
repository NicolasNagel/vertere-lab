import { useMutation, useQueryClient } from '@tanstack/react-query'

import { confirmAttendance, type AttendanceConfirmItemInput } from './attendances-api'

interface ConfirmAttendanceVariables {
  attendanceId: string
  items: AttendanceConfirmItemInput[]
  idempotencyKey: string
}

export function useConfirmAttendanceMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ attendanceId, items, idempotencyKey }: ConfirmAttendanceVariables) =>
      confirmAttendance(attendanceId, items, idempotencyKey),
    onSuccess: (attendance) => {
      void queryClient.invalidateQueries({ queryKey: ['attendances'] })
      queryClient.setQueryData(['attendances', 'detail', attendance.id], attendance)
    },
  })
}
