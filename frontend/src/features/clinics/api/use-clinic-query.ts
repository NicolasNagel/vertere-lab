import { useQuery } from '@tanstack/react-query'

import { fetchClinic } from './clinics-api'

export function clinicQueryKey(id: string) {
  return ['clinics', 'detail', id] as const
}

export function useClinicQuery(id: string | null) {
  return useQuery({
    queryKey: clinicQueryKey(id ?? ''),
    queryFn: () => fetchClinic(id as string),
    enabled: id !== null,
  })
}
