import { useEffect, useRef, useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'

interface ClosureReopenModalProps {
  isPending: boolean
  error: Error | null
  onCancel: () => void
  onConfirm: (reason: string) => void
}

export function ClosureReopenModal({
  isPending,
  error,
  onCancel,
  onConfirm,
}: ClosureReopenModalProps) {
  const [reason, setReason] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const submittedRef = useRef(false)
  const isValid = reason.trim().length >= 10

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  useEffect(() => {
    if (error) submittedRef.current = false
  }, [error])

  return (
    <div className="closure-reopen-modal__backdrop" role="presentation" onMouseDown={onCancel}>
      <section
        aria-labelledby="closure-reopen-title"
        aria-modal="true"
        className="closure-reopen-modal"
        role="dialog"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id="closure-reopen-title">Reabrir fechamento</h2>
        <p>
          Os atendimentos voltarão a ficar disponíveis para correção. O snapshot desta versão
          continuará preservado.
        </p>
        <label htmlFor="closure-reopen-reason">Justificativa</label>
        <textarea
          ref={textareaRef}
          id="closure-reopen-reason"
          rows={4}
          maxLength={1000}
          value={reason}
          disabled={isPending}
          onChange={(event) => setReason(event.target.value)}
        />
        {error && (
          <p role="alert" className="closure-detail-page__error">
            {error instanceof ApiError ? error.message : 'Não foi possível reabrir o fechamento.'}
          </p>
        )}
        <div className="closure-reopen-modal__actions">
          <Button type="button" variant="ghost" disabled={isPending} onClick={onCancel}>
            Cancelar
          </Button>
          <Button
            type="button"
            disabled={!isValid || isPending}
            onClick={() => {
              if (submittedRef.current) return
              submittedRef.current = true
              onConfirm(reason.trim())
            }}
          >
            {isPending ? 'Reabrindo…' : 'Confirmar reabertura'}
          </Button>
        </div>
      </section>
    </div>
  )
}
