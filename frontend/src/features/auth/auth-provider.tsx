import { useEffect, type ReactNode } from 'react'

import { useMeQuery } from './api/use-me-query'
import { AuthContext, type AuthContextValue, type AuthStatus } from './auth-context'
import { markSessionActive } from './session-flag'

export function AuthProvider({ children }: { children: ReactNode }) {
  const meQuery = useMeQuery()

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

  const value: AuthContextValue = { status, user: meQuery.data ?? null }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
