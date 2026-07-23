/** Estado passado via `react-router` ao redirecionar para /login. */
export interface LoginRedirectState {
  reason?: 'session-expired'
}
