import { useQuery } from '@tanstack/react-query'

import { fetchPatientsSummary, type PatientsSummaryParams } from './patients-api'

/** Chave sob `['patients']`: toda mutação que invalida pacientes também refaz as contagens. */
export function usePatientsSummaryQuery(params: PatientsSummaryParams = {}) {
  return useQuery({
    queryKey: ['patients', 'summary', params] as const,
    queryFn: () => fetchPatientsSummary(params),
  })
}
