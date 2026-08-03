import { useQuery } from '@tanstack/react-query'

import { fetchOnCallFeeSettings } from './on-call-fee-settings-api'

export function useOnCallFeeSettingsQuery() {
  return useQuery({
    queryKey: ['on-call-fee-settings'],
    queryFn: fetchOnCallFeeSettings,
  })
}
