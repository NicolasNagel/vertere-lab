import { useQuery } from '@tanstack/react-query'

import { fetchAllPages } from '../../../shared/api/fetch-all-pages'
import { fetchClinics, type ClinicListParams } from './clinics-api'

export function clinicsQueryKey(params: ClinicListParams) {
  return ['clinics', params] as const
}

export function useClinicsQuery(params: ClinicListParams = {}) {
  return useQuery({
    queryKey: clinicsQueryKey(params),
    queryFn: () => fetchClinics(params),
  })
}

export function useAllClinicsQuery(params: ClinicListParams = {}) {
  return useQuery({
    queryKey: ['clinics', 'all', params],
    queryFn: () => fetchAllPages(fetchClinics, params),
  })
}
