import { createContext, useContext } from 'react'

import type { AuthenticatedUser } from './api/auth-api'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export interface AuthContextValue {
  status: AuthStatus
  user: AuthenticatedUser | null
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useOptionalAuth(): AuthContextValue | null {
  return useContext(AuthContext)
}

export function useAuth(): AuthContextValue {
  const context = useOptionalAuth()
  if (context === null) {
    throw new Error('useAuth deve ser usado dentro de <AuthProvider>.')
  }
  return context
}
