import { createContext, useContext, useEffect, type ReactNode } from 'react'

import type { AuthenticatedUser } from './api/auth-api'
import { useMeQuery } from './api/use-me-query'
import { markSessionActive } from './session-flag'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

interface AuthContextValue {
  status: AuthStatus
  user: AuthenticatedUser | null
}

const AuthContext = createContext<AuthContextValue | null>(null)

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

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth deve ser usado dentro de <AuthProvider>.')
  }
  return context
}
