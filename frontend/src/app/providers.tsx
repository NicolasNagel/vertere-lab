import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'

import { AuthProvider } from '../features/auth/auth-provider'
import { ApiError } from '../shared/api/errors'

// Erro de cliente (4xx: sem permissão, não encontrado, dado inválido) nunca
// melhora ao tentar de novo — só um erro de rede/servidor (5xx) é transiente.
// Sem isso, uma query de uma tela sem permissão fica presa em `pending`
// aguardando a segunda tentativa (achado em teste manual: `isForbidden` nunca
// resolvia porque a query nunca chegava a `error`).
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return false
  }
  return failureCount < 1
}

export function AppProviders({ children }: { children: ReactNode }) {
  // useState garante um QueryClient estável por montagem da árvore.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: shouldRetry,
            refetchOnWindowFocus: false,
          },
        },
      }),
  )
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  )
}
