import { useQuery } from '@tanstack/react-query'

import { fetchAllPages } from '../../../shared/api/fetch-all-pages'
import { fetchExams } from './catalog-api'

/** Catálogo ativo inteiro (todas as páginas) — usado pela grade de exames do protocolo. */
export function useAllActiveExamsQuery() {
  return useQuery({
    queryKey: ['exams', 'all-active'] as const,
    queryFn: () => fetchAllPages((page) => fetchExams({ ...page, status: 'ACTIVE' }), {}),
  })
}
