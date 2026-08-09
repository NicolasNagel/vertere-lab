import { useQuery } from '@tanstack/react-query'

import { fetchClosurePreview, type ClosurePreviewParams } from './closures-api'

export function closurePreviewQueryKey(params: ClosurePreviewParams) {
  return ['closure-preview', params.clinicId, params.periodStart, params.periodEnd] as const
}

export function useClosurePreviewQuery(params: ClosurePreviewParams | null) {
  return useQuery({
    queryKey: params ? closurePreviewQueryKey(params) : ['closure-preview', 'idle'],
    queryFn: () => fetchClosurePreview(params as ClosurePreviewParams),
    enabled: params !== null,
  })
}
