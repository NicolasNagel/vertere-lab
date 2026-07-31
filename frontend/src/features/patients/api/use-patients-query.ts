import { useQuery } from '@tanstack/react-query'

import { fetchPatients, type PatientListParams } from './patients-api'

export function patientsQueryKey(params: PatientListParams) {
  return ['patients', params] as const
}

export function usePatientsQuery(params: PatientListParams | null = {}) {
  return useQuery({
    queryKey: params ? patientsQueryKey(params) : ['patients', 'idle'],
    queryFn: () => fetchPatients(params as PatientListParams),
    enabled: params !== null,
  })
}
