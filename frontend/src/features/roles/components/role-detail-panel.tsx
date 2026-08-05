import { useEffect, useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { ToggleSwitch } from '../../../shared/ui/toggle-switch'
import type { Permission, Role } from '../api/roles-api'
import { groupPermissionsByCategory } from '../lib/permission-groups'
import './role-detail-panel.css'

const SCOPE_LABELS: Record<Role['scope'], string> = {
  GLOBAL: 'Global',
  LAB: 'Laboratório',
  CLINIC: 'Clínica',
}

function describeError(error: unknown): { message: string; isConflict: boolean } | null {
  if (error === null || error === undefined) {
    return null
  }
  if (error instanceof ApiError) {
    return { message: error.message, isConflict: error.status === 409 }
  }
  return { message: 'Falha de conexão. Verifique sua internet e tente novamente.', isConflict: false }
}

interface RoleDetailPanelProps {
  role: Role | null
  isLoading: boolean
  canManage: boolean
  allPermissions: Permission[]
  appliedUserCount: number
  submitting: boolean
  error?: unknown
  onSave: (permissionCodes: string[], expectedRowVersion: number) => void
  onReload: () => void
}

export function RoleDetailPanel({
  role,
  isLoading,
  canManage,
  allPermissions,
  appliedUserCount,
  submitting,
  error,
  onSave,
  onReload,
}: RoleDetailPanelProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set())

  useEffect(() => {
    setSelected(new Set(role?.permissions ?? []))
  }, [role])

  if (isLoading) {
    return (
      <div className="role-detail-panel">
        <p className="role-detail-panel__empty">Carregando…</p>
      </div>
    )
  }

  if (!role) {
    return (
      <div className="role-detail-panel">
        <p className="role-detail-panel__empty">Selecione um perfil na lista ao lado.</p>
      </div>
    )
  }

  const groups = groupPermissionsByCategory(allPermissions)
  const originalPermissions = new Set(role.permissions)
  const isDirty =
    selected.size !== originalPermissions.size ||
    [...selected].some((code) => !originalPermissions.has(code))

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

  const errorInfo = describeError(error)

  return (
    <div className="role-detail-panel">
      <div className="role-detail-panel__badge">Editando perfil</div>
      <h2 className="role-detail-panel__title">Perfil {role.name}</h2>
      <p className="role-detail-panel__subtitle">
        {SCOPE_LABELS[role.scope]} · aplicado a {appliedUserCount}{' '}
        {appliedUserCount === 1 ? 'usuário' : 'usuários'}
        {role.isSystem ? ' · definido pelo sistema' : ''}
      </p>

      {groups.map((group) => (
        <div key={group.category} className="role-detail-panel__group">
          <div className="role-detail-panel__group-title">{group.label}</div>
          <div className="role-detail-panel__group-rows">
            {group.permissions.map((permission) => {
              const isLockedByMaster = permission.masterOnly && role.scope !== 'GLOBAL'
              return (
                <ToggleSwitch
                  key={permission.id}
                  label={permission.description || permission.code}
                  description={
                    isLockedByMaster ? (
                      <span className="role-detail-panel__master-lock">Definido pelo Master</span>
                    ) : undefined
                  }
                  checked={selected.has(permission.code)}
                  disabled={!canManage || submitting || isLockedByMaster}
                  onChange={() => toggle(permission.code)}
                />
              )
            })}
          </div>
        </div>
      ))}

      {errorInfo && (
        <div role="alert" className="role-detail-panel__domain-error">
          <p>{errorInfo.message}</p>
          {errorInfo.isConflict && (
            <Button type="button" variant="ghost" onClick={onReload}>
              Recarregar
            </Button>
          )}
        </div>
      )}

      {canManage && (
        <div className="role-detail-panel__actions">
          <Button
            type="button"
            variant="ghost"
            onClick={() => setSelected(new Set(role.permissions))}
            disabled={submitting || !isDirty}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            className="role-detail-panel__submit"
            disabled={submitting || !isDirty}
            onClick={() => onSave([...selected], role.rowVersion)}
          >
            {submitting ? 'Salvando…' : 'Salvar permissões'}
          </Button>
        </div>
      )}
    </div>
  )
}
