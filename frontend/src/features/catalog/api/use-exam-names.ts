import { useQueries } from '@tanstack/react-query'

import { fetchExam } from './catalog-api'
import { examQueryKey } from './use-exam-query'

/** Nome de cada exame pelo id, buscando só os que a tela precisa (cache compartilhado com o
 * detalhe do exame). Evita depender de uma página fixa do catálogo. */
export function useExamNames(ids: string[]): Map<string, string> {
  const unique = [...new Set(ids)]
  const results = useQueries({
    queries: unique.map((id) => ({
      queryKey: examQueryKey(id),
      queryFn: () => fetchExam(id),
      staleTime: 60_000,
    })),
  })
  const names = new Map<string, string>()
  results.forEach((result, index) => {
    const id = unique[index]
    if (id && result.data) names.set(id, result.data.name)
  })
  return names
}
