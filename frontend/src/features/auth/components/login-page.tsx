import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../auth-provider'
import type { LoginRedirectState } from '../types'
import { AuthLayout } from './auth-layout'
import { LoginForm } from './login-form'

export function LoginPage() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'authenticated') {
    return <Navigate to="/" replace />
  }

  const redirectState = (location.state ?? null) as LoginRedirectState | null
  const notice =
    redirectState?.reason === 'session-expired'
      ? 'Sua sessão expirou. Faça login novamente.'
      : undefined

  return (
    <AuthLayout>
      <LoginForm notice={notice} />
    </AuthLayout>
  )
}
