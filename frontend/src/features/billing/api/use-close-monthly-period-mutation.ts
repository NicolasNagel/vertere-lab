import { useMutation, useQueryClient } from '@tanstack/react-query'

import { closeMonthlyPeriod, type CloseMonthlyPeriodParams } from './closures-api'
import { closurePreviewQueryKey } from './use-closure-preview-query'

export function useCloseMonthlyPeriodMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: CloseMonthlyPeriodParams) =>
      closeMonthlyPeriod(params, crypto.randomUUID()),
    onSuccess: (_closure, params) => {
      void queryClient.invalidateQueries({ queryKey: closurePreviewQueryKey(params) })
      void queryClient.invalidateQueries({ queryKey: ['monthly-closures'] })
    },
  })
}
