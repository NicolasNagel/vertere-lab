import { useState } from 'react'

import { describeError } from '../../../shared/api/describe-error'
import { Button } from '../../../shared/ui/button'
import { Checkbox } from '../../../shared/ui/checkbox'
import { Dropdown, type DropdownOption } from '../../../shared/ui/dropdown'
import { UsersIcon } from '../../../shared/ui/icons'
import './assign-role-dialog.css'
import type { Clinic } from '../../clinics/api/clinics-api'
import type { Role } from '../../roles/api/roles-api'

interface AssignRoleDialogProps {
  currentRoleId: string
  currentClinicIds: string[]
  roles: Role[]
  clinics: Clinic[]
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmit: (roleId: string, clinicIds: string[]) => void
}

export function AssignRoleDialog({
  currentRoleId,
  currentClinicIds,
  roles,
  clinics,
  submitting,
  error,
  onCancel,
  onSubmit,
}: AssignRoleDialogProps) {
  const [roleId, setRoleId] = useState(currentRoleId)
  const [clinicIds, setClinicIds] = useState(currentClinicIds)
  const [accessError, setAccessError] = useState<string | null>(null)
  const errorMessage = describeError(error)
  const selectedRole = roles.find((role) => role.id === roleId)
  const roleOptions: DropdownOption[] = roles.map((role) => ({ value: role.id, label: role.name }))
  const unchanged = roleId === currentRoleId && clinicIds.length === currentClinicIds.length &&
    clinicIds.every((id) => currentClinicIds.includes(id))

  return (
    <form
      className="assign-role-dialog"
      onSubmit={(event) => {
        event.preventDefault()
        const selectedClinicIds = selectedRole?.scope === 'CLINIC' ? clinicIds : []
        if (selectedRole?.scope === 'CLINIC' && selectedClinicIds.length === 0) {
          setAccessError('Selecione ao menos uma clínica.')
          return
        }
        onSubmit(roleId, selectedClinicIds)
      }}
    >
      <Dropdown
        variant="field"
        icon={<UsersIcon />}
        label="Novo perfil"
        disabled={submitting}
        options={roleOptions}
        value={roleId}
        onChange={setRoleId}
      />

      {selectedRole?.scope === 'CLINIC' && (
        <fieldset className="assign-role-dialog__clinics">
          <legend>Clínicas permitidas</legend>
          {clinics.map((clinic) => (
            <Checkbox
              key={clinic.id}
              label={clinic.name}
              checked={clinicIds.includes(clinic.id)}
              disabled={submitting}
              onChange={() => setClinicIds((current) => current.includes(clinic.id)
                ? current.filter((id) => id !== clinic.id)
                : [...current, clinic.id])}
            />
          ))}
        </fieldset>
      )}

      {accessError && <p role="alert" className="assign-role-dialog__domain-error">{accessError}</p>}

      {errorMessage && (
        <p role="alert" className="assign-role-dialog__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="assign-role-dialog__actions">
        <Button type="button" variant="cancel" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button
          type="submit"
          className="assign-role-dialog__submit"
          disabled={submitting || unchanged}
        >
          {submitting ? 'Salvando…' : 'Alterar perfil'}
        </Button>
      </div>
    </form>
  )
}
