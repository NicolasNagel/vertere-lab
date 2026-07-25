import { useQuery } from '@tanstack/react-query'

import { fetchSpecies } from './patients-api'

export function useSpeciesQuery() {
  return useQuery({
    queryKey: ['species'] as const,
    queryFn: fetchSpecies,
  })
}
