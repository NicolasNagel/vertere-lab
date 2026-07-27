import { ApiError } from './errors'

/** Erro de domínio (mensagem do backend) vs. falha de rede — nunca confundir
 * os dois na UI (rule: .claude/rules/frontend.md). */
export function describeError(error: unknown): string | null {
  if (error === null || error === undefined) {
    return null
  }
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}
