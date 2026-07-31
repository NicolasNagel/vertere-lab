import { useMutation, useQueryClient } from '@tanstack/react-query'

import { addFinancialAdjustment, type AddFinancialAdjustmentParams } from './closures-api'

export function useAddFinancialAdjustmentMutation(closureId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: AddFinancialAdjustmentParams) =>
      addFinancialAdjustment(closureId, params),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['monthly-closures'] })
    },
  })
}
