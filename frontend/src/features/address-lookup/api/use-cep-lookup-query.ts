import { useQuery } from '@tanstack/react-query'

import { fetchCepAddress } from './cep-api'

/** `rawCep` may still carry the display mask — normalize before deciding
 * whether there is enough to query. */
export function useCepLookupQuery(rawCep: string) {
  const cep = rawCep.replace(/\D/g, '')

  return useQuery({
    queryKey: ['cep-lookup', cep],
    queryFn: () => fetchCepAddress(cep),
    enabled: cep.length === 8,
    staleTime: Infinity,
    retry: false,
  })
}
