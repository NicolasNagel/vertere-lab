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
      // A prévia só existe para rascunho: refazê-la agora seria recusada (422), então fica de fora.
      void queryClient.invalidateQueries({
        queryKey: ['attendances'],
        predicate: (query) => query.queryKey[1] !== 'preview',
      })
      queryClient.setQueryData(['attendances', 'detail', attendance.id], attendance)
    },
  })
}
