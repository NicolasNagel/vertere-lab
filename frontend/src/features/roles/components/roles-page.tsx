import { useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { PlusIcon } from '../../../shared/ui/icons'
import { useAuth } from '../../auth/auth-context'
import { useUsersQuery } from '../../users/api/use-users-query'
import { useCreateRoleMutation } from '../api/use-create-role-mutation'
import { usePermissionsQuery } from '../api/use-permissions-query'
import { useRolesQuery } from '../api/use-roles-query'
import { useUpdateRoleMutation } from '../api/use-update-role-mutation'
import { RoleCreateForm } from './role-create-form'
import { RoleDetailPanel } from './role-detail-panel'
import { RoleList } from './role-list'
import './roles-page.css'

type PanelMode = 'view' | 'create'

export function RolesPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('roles.manage') ?? false

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<PanelMode>('view')

  const rolesQuery = useRolesQuery({ pageSize: 100 })
  const permissionsQuery = usePermissionsQuery()
  const usersQuery = useUsersQuery({ pageSize: 100 })

  const createMutation = useCreateRoleMutation()
  const updateMutation = useUpdateRoleMutation()

  const roles = rolesQuery.data?.items ?? []
  const allPermissions = permissionsQuery.data ?? []
  const selectedRole = roles.find((role) => role.id === selectedId) ?? null
  const appliedUserCount = selectedRole
    ? (usersQuery.data?.items ?? []).filter((item) => item.roleId === selectedRole.id).length
    : 0

  function handleSelect(id: string) {
    setSelectedId(id)
    setMode('view')
  }

  function handleStartCreate() {
    setSelectedId(null)
    setMode('create')
  }

  const isForbidden = rolesQuery.error instanceof ApiError && rolesQuery.error.status === 403

  return (
    <div className="roles-page">
      <div className="roles-page__header">
        <div>
          <div className="roles-page__eyebrow">Administração</div>
          <h1 className="roles-page__title">Perfis de permissão</h1>
        </div>
        {canManage && (
          <Button type="button" className="roles-page__new-button" onClick={handleStartCreate}>
            <PlusIcon /> Novo perfil
          </Button>
        )}
      </div>

      {isForbidden ? (
        <p className="roles-page__forbidden">
          Você não tem permissão para visualizar perfis de permissão.
        </p>
      ) : (
        <div className="roles-page__body">
          <RoleList
            roles={roles}
            selectedId={mode === 'create' ? null : selectedId}
            isLoading={rolesQuery.isLoading}
            onSelect={handleSelect}
          />

          {mode === 'create' ? (
            <div className="roles-page__create-panel">
              <h2 className="roles-page__create-title">Novo perfil</h2>
              <RoleCreateForm
                allPermissions={allPermissions}
                submitting={createMutation.isPending}
                error={createMutation.error}
                onCancel={() => setMode('view')}
                onSubmit={(values) =>
                  createMutation.mutate(values, {
                    onSuccess: (role) => {
                      setSelectedId(role.id)
                      setMode('view')
                    },
                  })
                }
              />
            </div>
          ) : (
            <RoleDetailPanel
              role={selectedRole}
              isLoading={selectedId !== null && rolesQuery.isLoading}
              canManage={canManage}
              allPermissions={allPermissions}
              appliedUserCount={appliedUserCount}
              submitting={updateMutation.isPending}
              error={updateMutation.error}
              onSave={(permissionCodes, expectedRowVersion) => {
                if (!selectedId) return
                updateMutation.mutate({
                  id: selectedId,
                  values: { permissions: permissionCodes, expectedRowVersion },
                })
              }}
              onReload={() => {
                updateMutation.reset()
                void rolesQuery.refetch()
              }}
            />
          )}
        </div>
      )}
    </div>
  )
}
