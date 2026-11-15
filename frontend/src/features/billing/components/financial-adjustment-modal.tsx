import { useEffect, useRef, useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { parseMoneyInput } from '../../../shared/lib/money'
import { Button } from '../../../shared/ui/button'
import { Modal } from '../../../shared/ui/modal'
import type { AddFinancialAdjustmentParams, FinancialAdjustmentKind } from '../api/closures-api'
import './closure-reopen-modal.css'

interface FinancialAdjustmentModalProps {
  isPending: boolean
  error: Error | null
  onCancel: () => void
  onConfirm: (params: AddFinancialAdjustmentParams) => void
}

export function FinancialAdjustmentModal({
  isPending,
  error,
  onCancel,
  onConfirm,
}: FinancialAdjustmentModalProps) {
  const [kind, setKind] = useState<FinancialAdjustmentKind>('DEBIT')
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const amountRef = useRef<HTMLInputElement>(null)
  const submittedRef = useRef(false)
  const parsedAmount = parseMoneyInput(amount)
  const isValid = parsedAmount !== null && reason.trim().length >= 10

  useEffect(() => {
    amountRef.current?.focus()
  }, [])

  useEffect(() => {
    if (error) submittedRef.current = false
  }, [error])

  return (
    <Modal
      titleId="adjustment-title"
      className="closure-reopen-modal"
      canDismiss={!isPending}
      dismissOnBackdrop
      onClose={onCancel}
    >
        <h2 id="adjustment-title">Adicionar ajuste</h2>
        <p>O ajuste será append-only e não modificará o snapshot original.</p>
        <label htmlFor="adjustment-kind">Tipo</label>
        <select
          id="adjustment-kind"
          value={kind}
          disabled={isPending}
          onChange={(event) => setKind(event.target.value as FinancialAdjustmentKind)}
        >
          <option value="DEBIT">Débito</option>
          <option value="CREDIT">Crédito</option>
        </select>
        <label htmlFor="adjustment-amount">Valor</label>
        <input
          ref={amountRef}
          id="adjustment-amount"
          inputMode="decimal"
          value={amount}
          disabled={isPending}
          onChange={(event) => setAmount(event.target.value)}
        />
        <label htmlFor="adjustment-reason">Justificativa</label>
        <textarea
          id="adjustment-reason"
          rows={4}
          maxLength={1000}
          value={reason}
          disabled={isPending}
          onChange={(event) => setReason(event.target.value)}
        />
        {error && (
          <p role="alert" className="closure-reopen-modal__error">
            {error instanceof ApiError ? error.message : 'Não foi possível adicionar o ajuste.'}
          </p>
        )}
        <div className="closure-reopen-modal__actions">
          <Button type="button" variant="cancel" disabled={isPending} onClick={onCancel}>
            Cancelar
          </Button>
          <Button
            type="button"
            disabled={!isValid || isPending}
            onClick={() => {
              if (submittedRef.current || parsedAmount === null) return
              submittedRef.current = true
              onConfirm({
                monthlyClosureItemId: null,
                kind,
                amount: parsedAmount,
                reason: reason.trim(),
              })
            }}
          >
            {isPending ? 'Salvando…' : 'Adicionar ajuste'}
          </Button>
        </div>
    </Modal>
  )
}
