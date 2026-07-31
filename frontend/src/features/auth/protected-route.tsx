import type { ReactNode } from 'react'
import { Navigate } from 'react-router'

import { useAuth } from './auth-context'
import { clearSessionFlag, hadActiveSession } from './session-flag'
import type { LoginRedirectState } from './types'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth()

  if (status === 'loading') {
    return null
  }

  if (status === 'anonymous') {
    const hadSession = hadActiveSession()
    if (hadSession) {
      clearSessionFlag()
    }
    const state: LoginRedirectState = hadSession ? { reason: 'session-expired' } : {}
    return <Navigate to="/login" replace state={state} />
  }

  return children
}
