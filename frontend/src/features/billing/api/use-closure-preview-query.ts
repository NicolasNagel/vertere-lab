import { useQuery } from '@tanstack/react-query'
import { useActorScopeKey } from '../../auth/use-actor-scope-key'

import { fetchClosurePreview, type ClosurePreviewParams } from './closures-api'

export function closurePreviewQueryKey(params: ClosurePreviewParams, actorScope = 'unknown') {
  return ['closure-preview', actorScope, params.clinicId, params.periodStart, params.periodEnd] as const
}

export function useClosurePreviewQuery(params: ClosurePreviewParams | null) {
  const actorScope = useActorScopeKey()
  return useQuery({
    queryKey: params
      ? closurePreviewQueryKey(params, actorScope)
      : ['closure-preview', actorScope, 'idle'],
    queryFn: () => fetchClosurePreview(params as ClosurePreviewParams),
    enabled: params !== null,
  })
}
