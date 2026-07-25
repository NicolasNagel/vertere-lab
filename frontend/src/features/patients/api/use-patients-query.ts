import { useQuery } from '@tanstack/react-query'

import { fetchPatients, type PatientListParams } from './patients-api'

export function patientsQueryKey(params: PatientListParams) {
  return ['patients', params] as const
}

export function usePatientsQuery(params: PatientListParams = {}) {
  return useQuery({
    queryKey: patientsQueryKey(params),
    queryFn: () => fetchPatients(params),
  })
}
