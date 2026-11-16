import { useQuery } from '@tanstack/react-query'

import { fetchOnCallFeeSettings } from './on-call-fee-settings-api'

/** `enabled` fica falso para quem não tem `pricing.read` (a API recusaria a leitura). */
export function useOnCallFeeSettingsQuery(enabled = true) {
  return useQuery({
    queryKey: ['on-call-fee-settings'],
    queryFn: fetchOnCallFeeSettings,
    enabled,
  })
}
