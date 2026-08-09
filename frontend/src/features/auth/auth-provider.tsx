import { useEffect, useRef, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { useMeQuery } from './api/use-me-query'
import { AuthContext, type AuthContextValue, type AuthStatus } from './auth-context'
import { markSessionActive } from './session-flag'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const meQuery = useMeQuery()
  const previousScope = useRef<string | null>(null)

  const status: AuthStatus = meQuery.isLoading
    ? 'loading'
    : meQuery.data
      ? 'authenticated'
      : 'anonymous'

  useEffect(() => {
    if (status === 'authenticated') {
      markSessionActive()
    }
  }, [status])

  useEffect(() => {
    const user = meQuery.data
    if (!user) return
    const scope = `${user.id}:${user.roleScope ?? 'unknown'}:${[...(user.clinicIds ?? [])].sort().join(',')}:${user.rowVersion ?? 0}`
    if (previousScope.current !== null && previousScope.current !== scope) {
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'auth' })
    }
    previousScope.current = scope
  }, [meQuery.data, queryClient])

  const value: AuthContextValue = { status, user: meQuery.data ?? null }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
