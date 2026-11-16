import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  updateOnCallFeeSetting,
  type OnCallFeeSettingUpdateInput,
  type OnCallServiceLevel,
} from './on-call-fee-settings-api'

interface UpdateOnCallFeeSettingVariables {
  serviceLevel: OnCallServiceLevel
  input: OnCallFeeSettingUpdateInput
}

export function useUpdateOnCallFeeSettingMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ serviceLevel, input }: UpdateOnCallFeeSettingVariables) =>
      updateOnCallFeeSetting(serviceLevel, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['on-call-fee-settings'],
      })
    },
  })
}
