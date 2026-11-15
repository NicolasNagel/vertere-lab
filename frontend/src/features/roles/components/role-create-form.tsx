import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { describeError } from '../../../shared/api/describe-error'
import { Button } from '../../../shared/ui/button'
import { SelectField } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import { ToggleSwitch } from '../../../shared/ui/toggle-switch'
import type { CreateRoleValues, Permission, Role } from '../api/roles-api'
import { groupPermissionsByCategory } from '../lib/permission-groups'
import './role-create-form.css'

const roleSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome do perfil.'),
  description: z.string().trim(),
})

type RoleFormFields = z.infer<typeof roleSchema>

const START_FROM_SCRATCH = ''

interface RoleCreateFormProps {
  allPermissions: Permission[]
  baseRoles: Role[]
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
  baseRoles,
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
  const [baseRoleId, setBaseRoleId] = useState(START_FROM_SCRATCH)

  const baseRoleOptions = [
    { value: START_FROM_SCRATCH, label: 'Começar do zero' },
    ...baseRoles.map((role) => ({ value: role.id, label: role.name })),
  ]

  function handleBaseRoleChange(roleId: string) {
    setBaseRoleId(roleId)
    const baseRole = baseRoles.find((role) => role.id === roleId)
    // Perfis criados aqui são sempre escopo LAB — se o perfil-base for o
    // Master (o único hoje com permissão master-only), essa permissão nunca
    // pode vir marcada, senão o formulário mostraria um toggle "ligado" que
    // nem pode ser desmarcado (trava) e o envio seria rejeitado pelo backend.
    const masterOnlyCodes = new Set(
      allPermissions.filter((permission) => permission.masterOnly).map((permission) => permission.code),
    )
    const clonedPermissions = (baseRole?.permissions ?? []).filter(
      (code) => !masterOnlyCodes.has(code),
    )
    setSelected(new Set(clonedPermissions))
  }

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
  const groups = groupPermissionsByCategory(allPermissions)

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
      <SelectField
        id="role-base"
        label="Baseado em"
        disabled={submitting}
        options={baseRoleOptions}
        value={baseRoleId}
        onChange={(event) => handleBaseRoleChange(event.target.value)}
      />

      {groups.map((group) => (
        <div key={group.category} className="role-create-form__group">
          <div className="role-create-form__group-title">{group.label}</div>
          <div className="role-create-form__group-rows">
            {group.permissions.map((permission) => {
              // Perfis criados aqui são sempre escopo LAB (ROLE_SCOPE acima)
              // — nunca GLOBAL — então toda permissão master-only fica
              // travada, sem exceção, neste formulário.
              const isLockedByMaster = permission.masterOnly
              return (
                <ToggleSwitch
                  key={permission.id}
                  label={permission.description || permission.code}
                  description={
                    isLockedByMaster ? (
                      <span className="role-create-form__master-lock">Definido pelo Master</span>
                    ) : undefined
                  }
                  checked={selected.has(permission.code)}
                  disabled={submitting || isLockedByMaster}
                  onChange={() => toggle(permission.code)}
                />
              )
            })}
          </div>
        </div>
      ))}

      {errorMessage && (
        <p role="alert" className="role-create-form__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="role-create-form__actions">
        <Button type="button" variant="cancel" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" className="role-create-form__submit" disabled={submitting}>
          {submitting ? 'Criando…' : 'Criar perfil'}
        </Button>
      </div>
    </form>
  )
}
