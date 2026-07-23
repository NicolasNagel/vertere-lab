// Heurística client-side para distinguir "nunca logou" de "sessão expirou":
// não existe endpoint que informe isso — inferimos a partir da última vez
// que /auth/me respondeu com sucesso nesta aba. Não é dado sensível, só um
// marcador de UX.
const SESSION_FLAG_KEY = 'vertere:had-active-session'

export function markSessionActive(): void {
  sessionStorage.setItem(SESSION_FLAG_KEY, '1')
}

export function hadActiveSession(): boolean {
  return sessionStorage.getItem(SESSION_FLAG_KEY) === '1'
}

export function clearSessionFlag(): void {
  sessionStorage.removeItem(SESSION_FLAG_KEY)
}
