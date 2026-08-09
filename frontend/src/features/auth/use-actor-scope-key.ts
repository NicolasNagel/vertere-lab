import { useOptionalAuth } from './auth-context'

export function useActorScopeKey(): string {
  const user = useOptionalAuth()?.user
  if (!user) return 'anonymous'
  return `${user.id}:${user.roleScope ?? 'unknown'}:${[...(user.clinicIds ?? [])].sort().join(',')}:${user.rowVersion ?? 0}`
}
