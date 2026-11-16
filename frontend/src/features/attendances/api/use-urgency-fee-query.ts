import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { fetchUrgencyFee, updateUrgencyFee } from './urgency-fee-api'

export const URGENCY_FEE_QUERY_KEY = ['urgency-fee-setting'] as const

/** `enabled` fica falso para quem não tem `pricing.read` (a API recusaria a leitura). */
export function useUrgencyFeeQuery(enabled = true) {
  return useQuery({
    queryKey: URGENCY_FEE_QUERY_KEY,
    queryFn: fetchUrgencyFee,
    enabled,
  })
}

export function useUpdateUrgencyFeeMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateUrgencyFee,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: URGENCY_FEE_QUERY_KEY }),
  })
}
