import { useQuery } from '@tanstack/react-query'

import { fetchClosureByPeriod, type ClosurePreviewParams } from './closures-api'

// Namespaced under `monthly-closures` (not a sibling of `closure-preview`) so
// that the close/reopen/adjustment mutations, which already invalidate
// `['monthly-closures']` broadly, refetch this query too without needing to
// know about it individually.
export function closureByPeriodQueryKey(params: ClosurePreviewParams) {
  return [
    'monthly-closures',
    'by-period',
    params.clinicId,
    params.periodStart,
    params.periodEnd,
  ] as const
}

export function useClosureByPeriodQuery(params: ClosurePreviewParams | null) {
  return useQuery({
    queryKey: params ? closureByPeriodQueryKey(params) : ['monthly-closures', 'by-period', 'idle'],
    queryFn: () => fetchClosureByPeriod(params as ClosurePreviewParams),
    enabled: params !== null,
  })
}
