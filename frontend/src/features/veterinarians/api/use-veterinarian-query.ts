import { useQuery } from '@tanstack/react-query'

import { fetchVeterinarian } from './veterinarians-api'

export function veterinarianQueryKey(id: string) {
  return ['veterinarians', 'detail', id] as const
}

export function useVeterinarianQuery(id: string | null) {
  return useQuery({
    queryKey: veterinarianQueryKey(id ?? ''),
    queryFn: () => fetchVeterinarian(id as string),
    enabled: id !== null,
  })
}
