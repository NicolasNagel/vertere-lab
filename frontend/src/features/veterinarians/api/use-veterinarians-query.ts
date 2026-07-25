import { useQuery } from '@tanstack/react-query'

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
