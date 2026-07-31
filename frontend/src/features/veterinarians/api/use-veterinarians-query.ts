import { useQuery } from '@tanstack/react-query'

import { fetchAllPages } from '../../../shared/api/fetch-all-pages'
import { fetchVeterinarians, type VeterinarianListParams } from './veterinarians-api'

export function veterinariansQueryKey(params: VeterinarianListParams) {
  return ['veterinarians', params] as const
}

export function useVeterinariansQuery(params: VeterinarianListParams = {}) {
  return useQuery({
    queryKey: veterinariansQueryKey(params),
    queryFn: () => fetchVeterinarians(params),
  })
}

export function useAllVeterinariansQuery(params: VeterinarianListParams | null = {}) {
  return useQuery({
    queryKey: params ? ['veterinarians', 'all', params] : ['veterinarians', 'all', 'idle'],
    queryFn: () => fetchAllPages(fetchVeterinarians, params as VeterinarianListParams),
    enabled: params !== null,
  })
}
