import { useMutation, useQueryClient } from '@tanstack/react-query'

import { reopenMonthlyClosure } from './closures-api'
import { monthlyClosureQueryKey } from './use-monthly-closure-query'

export function useReopenMonthlyClosureMutation(closureId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reason: string) => reopenMonthlyClosure(closureId, reason),
    onSuccess: async (closure) => {
      queryClient.setQueryData(monthlyClosureQueryKey(closureId), closure)
      await queryClient.invalidateQueries({ queryKey: ['monthly-closures'] })
    },
  })
}
