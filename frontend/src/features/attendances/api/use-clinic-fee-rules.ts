import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createClinicFeeRule,
  fetchClinicFeeRules,
  updateClinicFeeRule,
  type ClinicFeeRuleValues,
} from './clinic-fee-rules-api'

const KEY = ['clinic-fee-rules'] as const

export function useClinicFeeRulesQuery(clinicId?: string) {
  return useQuery({
    queryKey: [...KEY, clinicId ?? 'all'],
    queryFn: () => fetchClinicFeeRules(clinicId),
  })
}

export function useCreateClinicFeeRuleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createClinicFeeRule,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

interface UpdateVariables {
  id: string
  input: ClinicFeeRuleValues & {
    isActive: boolean
    expectedRowVersion: number
  }
}

export function useUpdateClinicFeeRuleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: UpdateVariables) => updateClinicFeeRule(id, input),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: KEY }),
  })
}
