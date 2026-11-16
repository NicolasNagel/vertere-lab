import { useRef, useState } from 'react'

import { describeError } from '../../../shared/api/describe-error'
import { ApiError } from '../../../shared/api/errors'
import { formatCurrencyBRL, formatDate } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import { Modal } from '../../../shared/ui/modal'
import { useCloseMonthlyPeriodMutation } from '../api/use-close-monthly-period-mutation'
import type { ClosurePreview, MonthlyClosure } from '../api/closures-api'
import './closure-close-modal.css'

interface ClosureCloseModalProps {
  clinicName: string
  preview: ClosurePreview
  onClose: () => void
  onClosed: (closure: MonthlyClosure) => void
}

/** Passo de confirmação explícito antes de fechar — nunca um clique só
 * (`.claude/rules/05-frontend-web-mobile.md`: "confirmação de fechamento é
 * um passo explícito, não um clique acidental"). */
export function ClosureCloseModal({
  clinicName,
  preview,
  onClose,
  onClosed,
}: ClosureCloseModalProps) {
  const [confirmed, setConfirmed] = useState(false)
  const submissionStarted = useRef(false)
  const closeMutation = useCloseMonthlyPeriodMutation()

  const errorMessage = describeError(closeMutation.error)
  const isAlreadyClosed =
    closeMutation.error instanceof ApiError && closeMutation.error.code === 'CLOSURE_ALREADY_EXISTS'

  function handleConfirm() {
    if (!confirmed || submissionStarted.current) return
    submissionStarted.current = true
    closeMutation.mutate(
      {
        clinicId: preview.clinicId,
        periodStart: preview.periodStart,
        periodEnd: preview.periodEnd,
      },
      {
        onSuccess: onClosed,
        onError: () => {
          submissionStarted.current = false
        },
      },
    )
  }

  return (
    <Modal
      titleId="closure-close-modal-title"
      className="closure-close-modal"
      canDismiss={!closeMutation.isPending}
      onClose={onClose}
    >
        <h2 id="closure-close-modal-title" className="closure-close-modal__title">
          Fechar período
        </h2>

        <div className="closure-close-modal__summary">
          <div className="closure-close-modal__summary-row">
            <span>Clínica</span>
            <span>{clinicName}</span>
          </div>
          <div className="closure-close-modal__summary-row">
            <span>Período</span>
            <span>
              {formatDate(preview.periodStart)} – {formatDate(preview.periodEnd)}
            </span>
          </div>
          <div className="closure-close-modal__summary-row">
            <span>Itens elegíveis</span>
            <span>{preview.itemCount}</span>
          </div>
          <div className="closure-close-modal__summary-row closure-close-modal__summary-row--total">
            <span>Total</span>
            <span>{formatCurrencyBRL(preview.grandTotal)}</span>
          </div>
        </div>

        <label>
          <input
            type="checkbox"
            checked={confirmed}
            disabled={closeMutation.isPending}
            onChange={(event) => setConfirmed(event.target.checked)}
          />{' '}
          Confirmo que revisei a prévia e quero fechar este período. Esta ação não pode ser
          desfeita.
        </label>

        {errorMessage && (
          <p className="closure-close-modal__error" role="alert">
            {errorMessage}
            {isAlreadyClosed && ' Recarregue a prévia para ver o estado atual.'}
          </p>
        )}

        <div className="closure-close-modal__actions">
          <Button type="button" variant="secondary" disabled={closeMutation.isPending} onClick={onClose}>
            Voltar
          </Button>
          <Button type="button" disabled={!confirmed || closeMutation.isPending} onClick={handleConfirm}>
            {closeMutation.isPending ? 'Fechando…' : 'Fechar período'}
          </Button>
        </div>
    </Modal>
  )
}
