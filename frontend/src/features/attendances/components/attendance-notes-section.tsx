import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { describeError } from '../../../shared/api/describe-error'
import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { attendanceQueryKey } from '../api/use-attendance-query'
import { useUpdateAttendanceMutation } from '../api/use-update-attendance-mutation'
import type { Attendance } from '../api/attendances-api'
import './attendance-notes-section.css'

interface AttendanceNotesSectionProps {
  attendance: Attendance
  canEdit: boolean
}

/** `AttendanceRecord.update_fields` only allows editing `notes` once an
 * attendance is `CONFIRMED` — every other header field is locked because
 * `service_date` drives `billing_competence`
 * (`.claude/rules/12-attendance.md`). The caller only renders this for
 * `CONFIRMED`; `canEdit` gates the button itself on `attendances.update`. */
export function AttendanceNotesSection({ attendance, canEdit }: AttendanceNotesSectionProps) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [draftNotes, setDraftNotes] = useState(attendance.notes ?? '')
  const updateMutation = useUpdateAttendanceMutation()

  const errorMessage = describeError(updateMutation.error)
  const isConflict = updateMutation.error instanceof ApiError && updateMutation.error.status === 409

  function startEditing() {
    setDraftNotes(attendance.notes ?? '')
    updateMutation.reset()
    setEditing(true)
  }

  function handleSave() {
    updateMutation.mutate(
      {
        attendanceId: attendance.id,
        rowVersion: attendance.rowVersion,
        input: { notes: draftNotes },
      },
      { onSuccess: () => setEditing(false) },
    )
  }

  function handleReload() {
    void queryClient.invalidateQueries({ queryKey: attendanceQueryKey(attendance.id) })
    setEditing(false)
  }

  return (
    <section className="attendance-readonly-detail__section">
      <div className="attendance-notes-section__header">
        <h2 className="attendance-readonly-detail__section-title">Observações</h2>
        {canEdit && !editing && (
          <button type="button" className="attendance-notes-section__edit-button" onClick={startEditing}>
            Editar
          </button>
        )}
      </div>

      {!editing && (
        <p className="attendance-notes-section__text">
          {attendance.notes || 'Nenhuma observação registrada.'}
        </p>
      )}

      {editing && (
        <div className="attendance-notes-section__form">
          <TextField
            id="attendance-notes-edit"
            label="Observações"
            disabled={updateMutation.isPending}
            value={draftNotes}
            onChange={(event) => setDraftNotes(event.target.value)}
          />

          {errorMessage && (
            <p className="attendance-notes-section__error" role="alert">
              {errorMessage}
            </p>
          )}

          <div className="attendance-notes-section__actions">
            <Button type="button" disabled={updateMutation.isPending} onClick={handleSave}>
              {updateMutation.isPending ? 'Salvando…' : 'Salvar'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={updateMutation.isPending}
              onClick={() => setEditing(false)}
            >
              Cancelar
            </Button>
            {isConflict && (
              <Button type="button" variant="ghost" onClick={handleReload}>
                Recarregar atendimento
              </Button>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
