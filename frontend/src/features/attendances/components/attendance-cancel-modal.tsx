import { useState } from 'react'

import { describeError } from '../../../shared/api/describe-error'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { useCancelAttendanceMutation } from '../api/use-cancel-attendance-mutation'
import type { Attendance } from '../api/attendances-api'
import './attendance-cancel-modal.css'

interface AttendanceCancelModalProps {
  attendance: Attendance
  onCancelled: (attendance: Attendance) => void
  onClose: () => void
}

export function AttendanceCancelModal({
  attendance,
  onCancelled,
  onClose,
}: AttendanceCancelModalProps) {
  const [reason, setReason] = useState('')
  const cancelMutation = useCancelAttendanceMutation()

  const trimmedReason = reason.trim()
  const errorMessage = describeError(cancelMutation.error)

  function handleConfirm() {
    if (!trimmedReason) return
    cancelMutation.mutate(
      { attendanceId: attendance.id, reason: trimmedReason },
      { onSuccess: onCancelled },
    )
  }

  return (
    <div className="attendance-cancel-modal__backdrop" role="presentation">
      <div
        className="attendance-cancel-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="attendance-cancel-modal-title"
      >
        <h2 id="attendance-cancel-modal-title" className="attendance-cancel-modal__title">
          Cancelar atendimento
        </h2>
        <p className="attendance-cancel-modal__hint">
          {attendance.protocolNumber
            ? `Protocolo ${attendance.protocolNumber}. `
            : 'Este atendimento ainda não tem protocolo. '}
          Essa ação não pode ser desfeita.
        </p>

        <TextField
          id="attendance-cancel-reason"
          label="Motivo do cancelamento"
          disabled={cancelMutation.isPending}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          errorMessage={reason.length > 0 && !trimmedReason ? 'Informe um motivo.' : undefined}
        />

        {errorMessage && (
          <p className="attendance-cancel-modal__error" role="alert">
            {errorMessage}
          </p>
        )}

        <div className="attendance-cancel-modal__actions">
          <Button type="button" variant="ghost" disabled={cancelMutation.isPending} onClick={onClose}>
            Voltar
          </Button>
          <Button
            type="button"
            disabled={!trimmedReason || cancelMutation.isPending}
            onClick={handleConfirm}
          >
            {cancelMutation.isPending ? 'Cancelando…' : 'Confirmar cancelamento'}
          </Button>
        </div>
      </div>
    </div>
  )
}
