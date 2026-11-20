import { useCallback, useState } from 'react'

import { describeError } from '../api/describe-error'

/**
 * Mensagem de falha de uma ação disparada numa lista (inativar, reativar): sem isso, um 409 ou 403
 * não aparecia para ninguém. Some ao tentar de novo ou quando a próxima ação dá certo.
 */
export function useActionError() {
  const [message, setMessage] = useState<string | null>(null)
  const onError = useCallback((error: unknown) => setMessage(describeError(error)), [])
  const clear = useCallback(() => setMessage(null), [])
  return { message, onError, clear }
}
