import { useState } from 'react'

import { describeError } from '../../../shared/api/describe-error'
import { Button } from '../../../shared/ui/button'
import { SelectField, type SelectOption } from '../../../shared/ui/select'
import './assign-role-dialog.css'

interface AssignRoleDialogProps {
  currentRoleId: string
  roleOptions: SelectOption[]
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmit: (roleId: string) => void
}

export function AssignRoleDialog({
  currentRoleId,
  roleOptions,
  submitting,
  error,
  onCancel,
  onSubmit,
}: AssignRoleDialogProps) {
  const [roleId, setRoleId] = useState(currentRoleId)
  const errorMessage = describeError(error)

  return (
    <form
      className="assign-role-dialog"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit(roleId)
      }}
    >
      <SelectField
        id="assign-role-select"
        label="Novo perfil"
        disabled={submitting}
        options={roleOptions}
        value={roleId}
        onChange={(event) => setRoleId(event.target.value)}
      />

      {errorMessage && (
        <p role="alert" className="assign-role-dialog__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="assign-role-dialog__actions">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button
          type="submit"
          className="assign-role-dialog__submit"
          disabled={submitting || roleId === currentRoleId}
        >
          {submitting ? 'Salvando…' : 'Alterar perfil'}
        </Button>
      </div>
    </form>
  )
}
