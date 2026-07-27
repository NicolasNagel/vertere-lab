import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { describeError } from '../../../shared/api/describe-error'
import { Button } from '../../../shared/ui/button'
import { SelectField, type SelectOption } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import type { CreateUserValues } from '../api/users-api'
import './user-form.css'

const userSchema = z.object({
  email: z.string().trim().min(1, 'Informe o e-mail.').email('Informe um e-mail válido.'),
  fullName: z.string().trim().min(1, 'Informe o nome completo.'),
  roleId: z.string().trim().min(1, 'Selecione um perfil.'),
})

type UserFormFields = z.infer<typeof userSchema>

interface UserFormProps {
  roleOptions: SelectOption[]
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmit: (values: CreateUserValues) => void
}

export function UserForm({ roleOptions, submitting, error, onCancel, onSubmit }: UserFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<UserFormFields>({
    resolver: zodResolver(userSchema),
    defaultValues: { email: '', fullName: '', roleId: '' },
  })

  const submit = handleSubmit((fields) => {
    onSubmit({ email: fields.email, fullName: fields.fullName, roleId: fields.roleId })
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
