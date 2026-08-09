import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { describeError } from '../../../shared/api/describe-error'
import { Button } from '../../../shared/ui/button'
import { Checkbox } from '../../../shared/ui/checkbox'
import { SelectField, type SelectOption } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import type { CreateUserValues } from '../api/users-api'
import type { Clinic } from '../../clinics/api/clinics-api'
import type { Role } from '../../roles/api/roles-api'
import './user-form.css'

const userSchema = z.object({
  email: z.string().trim().min(1, 'Informe o e-mail.').email('Informe um e-mail válido.'),
  fullName: z.string().trim().min(1, 'Informe o nome completo.'),
  roleId: z.string().trim().min(1, 'Selecione um perfil.'),
})

type UserFormFields = z.infer<typeof userSchema>

interface UserFormProps {
  roles: Role[]
  clinics: Clinic[]
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmit: (values: CreateUserValues) => void
}

export function UserForm({ roles, clinics, submitting, error, onCancel, onSubmit }: UserFormProps) {
  const [clinicIds, setClinicIds] = useState<string[]>([])
  const [accessError, setAccessError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<UserFormFields>({
    resolver: zodResolver(userSchema),
    defaultValues: { email: '', fullName: '', roleId: '' },
  })

  const selectedRole = roles.find((role) => role.id === watch('roleId'))
  const roleOptions: SelectOption[] = roles.map((role) => ({ value: role.id, label: role.name }))

  const submit = handleSubmit((fields) => {
    const selectedClinicIds = selectedRole?.scope === 'CLINIC' ? clinicIds : []
    if (selectedRole?.scope === 'CLINIC' && selectedClinicIds.length === 0) {
      setAccessError('Selecione ao menos uma clínica.')
      return
    }
    setAccessError(null)
    onSubmit({
      email: fields.email,
      fullName: fields.fullName,
      roleId: fields.roleId,
      clinicIds: selectedClinicIds,
    })
  })

  const errorMessage = describeError(error)

  return (
    <form className="user-form" onSubmit={submit} noValidate>
      <TextField
        id="user-full-name"
        label="Nome completo"
        disabled={submitting}
        errorMessage={errors.fullName?.message}
        {...register('fullName')}
      />

      <TextField
        id="user-email"
        label="E-mail"
        type="email"
        disabled={submitting}
        errorMessage={errors.email?.message}
        {...register('email')}
      />

      <SelectField
        id="user-role"
        label="Perfil"
        disabled={submitting}
        errorMessage={errors.roleId?.message}
        options={[{ value: '', label: 'Selecione um perfil' }, ...roleOptions]}
        {...register('roleId')}
      />

      {selectedRole?.scope === 'CLINIC' && (
        <fieldset className="user-form__clinics">
          <legend>Clínicas permitidas</legend>
          {clinics.map((clinic) => (
            <Checkbox
              key={clinic.id}
              label={clinic.name}
              checked={clinicIds.includes(clinic.id)}
              disabled={submitting}
              onChange={() =>
                setClinicIds((current) =>
                  current.includes(clinic.id)
                    ? current.filter((id) => id !== clinic.id)
                    : [...current, clinic.id],
                )
              }
            />
          ))}
        </fieldset>
      )}

      {accessError && <p role="alert" className="user-form__domain-error">{accessError}</p>}

      {errorMessage && (
        <p role="alert" className="user-form__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="user-form__actions">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" className="user-form__submit" disabled={submitting}>
          {submitting ? 'Criando…' : 'Criar usuário'}
        </Button>
      </div>
    </form>
  )
}
