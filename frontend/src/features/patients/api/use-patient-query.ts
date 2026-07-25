import { useQuery } from '@tanstack/react-query'

import { fetchPatient } from './patients-api'

export function patientQueryKey(id: string) {
  return ['patients', 'detail', id] as const
}

export function usePatientQuery(id: string | null) {
  return useQuery({
    queryKey: patientQueryKey(id ?? ''),
    queryFn: () => fetchPatient(id as string),
    enabled: id !== null,
  })
}
