import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { describeError } from '../../../shared/api/describe-error'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { ToggleSwitch } from '../../../shared/ui/toggle-switch'
import type { CreateRoleValues, Permission } from '../api/roles-api'
import { groupPermissionsByResource } from '../lib/permission-groups'
import './role-create-form.css'

const roleSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome do perfil.'),
  description: z.string().trim(),
})

type RoleFormFields = z.infer<typeof roleSchema>

interface RoleCreateFormProps {
  allPermissions: Permission[]
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmit: (values: CreateRoleValues) => void
}

// Escopo sempre `LAB`: perfis de escopo CLINIC dependem de `ClinicMembership`
// real, que ainda não existe (Fase 2) — ver Contexto do plano desta fatia.
const ROLE_SCOPE = 'LAB' as const

export function RoleCreateForm({
  allPermissions,
  submitting,
  error,
  onCancel,
  onSubmit,
}: RoleCreateFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RoleFormFields>({
    resolver: zodResolver(roleSchema),
    defaultValues: { name: '', description: '' },
  })
  const [selected, setSelected] = useState<Set<string>>(new Set())

  function toggle(code: string) {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(code)) {
        next.delete(code)
      } else {
        next.add(code)
      }
      return next
    })
  }

  const submit = handleSubmit((fields) => {
    onSubmit({
      name: fields.name,
      scope: ROLE_SCOPE,
      description: fields.description,
      permissions: [...selected],
    })
  })

  const errorMessage = describeError(error)
  const groups = groupPermissionsByResource(allPermissions)

  return (
    <form className="role-create-form" onSubmit={submit} noValidate>
      <TextField
        id="role-name"
        label="Nome do perfil"
        disabled={submitting}
        errorMessage={errors.name?.message}
        {...register('name')}
      />
      <TextField
        id="role-description"
        label="Descrição"
        disabled={submitting}
        {...register('description')}
      />

      {groups.map((group) => (
        <div key={group.resource} className="role-create-form__group">
          <div className="role-create-form__group-title">{group.label}</div>
          <div className="role-create-form__group-rows">
            {group.permissions.map((permission) => (
              <ToggleSwitch
                key={permission.id}
                label={permission.code}
                description={permission.description || undefined}
                checked={selected.has(permission.code)}
                disabled={submitting}
                onChange={() => toggle(permission.code)}
              />
            ))}
          </div>
        </div>
      ))}

      {errorMessage && (
        <p role="alert" className="role-create-form__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="role-create-form__actions">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" className="role-create-form__submit" disabled={submitting}>
          {submitting ? 'Criando…' : 'Criar perfil'}
        </Button>
      </div>
    </form>
  )
}
