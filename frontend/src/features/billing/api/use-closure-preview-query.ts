import { useQuery } from '@tanstack/react-query'

import { fetchClosurePreview, type ClosurePreviewParams } from './closures-api'

export function closurePreviewQueryKey(params: ClosurePreviewParams) {
  return ['closure-preview', params.clinicId, params.year, params.month] as const
}

export function useClosurePreviewQuery(params: ClosurePreviewParams | null) {
  return useQuery({
    queryKey: params ? closurePreviewQueryKey(params) : ['closure-preview', 'idle'],
    queryFn: () => fetchClosurePreview(params as ClosurePreviewParams),
    enabled: params !== null,
  })
}
