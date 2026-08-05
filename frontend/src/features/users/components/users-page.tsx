import { useEffect, useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { PlusIcon } from '../../../shared/ui/icons'
import type { SelectOption } from '../../../shared/ui/select'
import { useAuth } from '../../auth/auth-context'
import { RoleCreateForm } from '../../roles/components/role-create-form'
import { RoleDetailPanel } from '../../roles/components/role-detail-panel'
import { useCreateRoleMutation } from '../../roles/api/use-create-role-mutation'
import { usePermissionsQuery } from '../../roles/api/use-permissions-query'
import { useAllRolesQuery } from '../../roles/api/use-roles-query'
import { useUpdateRoleMutation } from '../../roles/api/use-update-role-mutation'
import { useActivateUserMutation } from '../api/use-activate-user-mutation'
import { useAssignRoleMutation } from '../api/use-assign-role-mutation'
import { useCreateUserMutation } from '../api/use-create-user-mutation'
import { useDeactivateUserMutation } from '../api/use-deactivate-user-mutation'
import { useAllUsersQuery, useUsersQuery } from '../api/use-users-query'
import type { CreatedUser } from '../api/users-api'
import { RoleChipList } from './role-chip-list'
import { TemporaryPasswordDialog } from './temporary-password-dialog'
import { UserForm } from './user-form'
import { UserList } from './user-list'
import './users-page.css'

type PanelMode = 'view' | 'create-user' | 'create-role'

export function UsersPage() {
  const { user } = useAuth()
  const canCreateUser = user?.permissions.includes('users.create') ?? false
  const canAssignRole = user?.permissions.includes('roles.assign') ?? false
  const canDeactivate = user?.permissions.includes('users.deactivate') ?? false
  const canActivate = user?.permissions.includes('users.activate') ?? false
  const canManageRoles = user?.permissions.includes('roles.manage') ?? false

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null)
  const [mode, setMode] = useState<PanelMode>('view')
  const [assigningRoleForId, setAssigningRoleForId] = useState<string | null>(null)
  const [createdUser, setCreatedUser] = useState<CreatedUser | null>(null)

  const listQuery = useUsersQuery({ search: search || undefined, page, pageSize: 25 })
  // Fase 2 ainda não tem `ClinicMembership` real: perfis de escopo CLINIC
  // (CLINIC_ADMIN/VETERINARIAN/CLINIC_STAFF) não têm permissão nem vínculo
  // funcional, então ficam fora da lista de perfis atribuíveis aqui.
  const rolesQuery = useAllRolesQuery()
  const permissionsQuery = usePermissionsQuery()
  const allUsersQuery = useAllUsersQuery()

  const createUserMutation = useCreateUserMutation()
  const assignRoleMutation = useAssignRoleMutation()
  const deactivateMutation = useDeactivateUserMutation()
  const activateMutation = useActivateUserMutation()
  const createRoleMutation = useCreateRoleMutation()
  const updateRoleMutation = useUpdateRoleMutation()

  const users = listQuery.data?.items ?? []
  const firstUserId = listQuery.data?.items[0]?.id
  const activeCount = users.filter((item) => item.isActive).length
  const selectedUser = users.find((item) => item.id === selectedId) ?? null

  const roles = rolesQuery.data?.items ?? []
  const chipRoles = roles.filter((role) => role.scope !== 'CLINIC')
  const allPermissions = permissionsQuery.data ?? []
  const selectedRole = roles.find((role) => role.id === selectedRoleId) ?? null
  const appliedUserCount = selectedRole
    ? (allUsersQuery.data?.items ?? []).filter((item) => item.roleId === selectedRole.id).length
    : 0

  useEffect(() => {
    if (mode === 'view' && selectedId === null && firstUserId) setSelectedId(firstUserId)
  }, [firstUserId, mode, selectedId])

  // Chip de perfil e linha de usuário são seleções independentes — este
  // efeito só cobre o valor inicial (sincroniza com o primeiro usuário, ou
  // com o primeiro perfil se ainda não houver usuário selecionado); depois
  // disso cada clique (linha ou chip) decide sozinho o que muda.
  useEffect(() => {
    if (mode !== 'view' || selectedRoleId !== null) return
    if (selectedUser) {
      setSelectedRoleId(selectedUser.roleId)
      return
    }
    const firstChipRole = chipRoles[0]
    if (firstChipRole) setSelectedRoleId(firstChipRole.id)
  }, [mode, selectedRoleId, selectedUser, chipRoles])

  const roleOptions: SelectOption[] = chipRoles.map((role) => ({
    value: role.id,
    label: role.name,
  }))

  const isForbidden = listQuery.error instanceof ApiError && listQuery.error.status === 403

  function handleSelect(id: string) {
    setSelectedId(id)
    const clickedUser = users.find((item) => item.id === id)
    if (clickedUser) setSelectedRoleId(clickedUser.roleId)
    setMode('view')
    setAssigningRoleForId(null)
    deactivateMutation.reset()
    activateMutation.reset()
  }

  function handleSelectRole(roleId: string) {
    setSelectedRoleId(roleId)
    setMode('view')
  }

  function handleStartCreateUser() {
    setSelectedId(null)
    setMode('create-user')
    setAssigningRoleForId(null)
  }

  function handleStartCreateRole() {
    setMode('create-role')
    setAssigningRoleForId(null)
  }

  return (
    <div className="users-page">
      <div className="users-page__header">
        <div>
          <div className="users-page__eyebrow">Administração</div>
          <h1 className="users-page__title">Usuários & Permissões</h1>
        </div>
        {canCreateUser && (
          <Button type="button" className="users-page__new-button" onClick={handleStartCreateUser}>
            <PlusIcon /> Novo usuário
          </Button>
        )}
      </div>

      {isForbidden ? (
        <p className="users-page__forbidden">Você não tem permissão para visualizar usuários.</p>
      ) : (
        <div className="users-page__body">
          <div className="users-page__roster">
            <RoleChipList
              roles={chipRoles}
              selectedRoleId={mode === 'view' ? selectedRoleId : null}
              canManageRoles={canManageRoles}
              onSelect={handleSelectRole}
              onCreateRole={handleStartCreateRole}
            />
            <UserList
              users={users}
              activeCount={activeCount}
              selectedId={mode === 'view' ? selectedId : null}
              search={search}
              isLoading={listQuery.isLoading}
              onSearchChange={(value) => {
                setSearch(value)
                setPage(1)
              }}
              onSelect={handleSelect}
              page={listQuery.data?.page ?? page}
              pageSize={listQuery.data?.pageSize ?? 25}
              total={listQuery.data?.total ?? 0}
              onPageChange={setPage}
              canAssignRole={canAssignRole}
              canDeactivate={canDeactivate}
              canActivate={canActivate}
              roleOptions={roleOptions}
              assigningRoleForId={assigningRoleForId}
              assignRoleSubmitting={assignRoleMutation.isPending}
              assignRoleError={assignRoleMutation.error}
              statusChangeError={deactivateMutation.error ?? activateMutation.error}
              onStartAssignRole={setAssigningRoleForId}
              onCancelAssignRole={() => {
                setAssigningRoleForId(null)
                assignRoleMutation.reset()
              }}
              onSubmitAssignRole={(id, roleId) =>
                assignRoleMutation.mutate(
                  { id, roleId },
                  { onSuccess: () => setAssigningRoleForId(null) },
                )
              }
              onDeactivate={(id) => deactivateMutation.mutate(id)}
              onActivate={(id) => activateMutation.mutate(id)}
            />
          </div>

          {mode === 'create-user' && (
            <div className="users-page__create-panel">
              <h2 className="users-page__create-title">Novo usuário</h2>
              <UserForm
                roleOptions={roleOptions}
                submitting={createUserMutation.isPending}
                error={createUserMutation.error}
                onCancel={() => setMode('view')}
                onSubmit={(values) =>
                  createUserMutation.mutate(values, {
                    onSuccess: (created) => {
                      setCreatedUser(created)
                      setSelectedId(created.user.id)
                      setMode('view')
                    },
                  })
                }
              />
            </div>
          )}

          {mode === 'create-role' && (
            <div className="users-page__create-panel">
              <h2 className="users-page__create-title">Novo perfil</h2>
              <RoleCreateForm
                allPermissions={allPermissions}
                baseRoles={chipRoles}
                submitting={createRoleMutation.isPending}
                error={createRoleMutation.error}
                onCancel={() => setMode('view')}
                onSubmit={(values) =>
                  createRoleMutation.mutate(values, {
                    onSuccess: () => setMode('view'),
                  })
                }
              />
            </div>
          )}

          {mode === 'view' && (
            <RoleDetailPanel
              role={selectedRole}
              isLoading={selectedRoleId !== null && rolesQuery.isLoading}
              canManage={canManageRoles}
              allPermissions={allPermissions}
              appliedUserCount={appliedUserCount}
              submitting={updateRoleMutation.isPending}
              error={updateRoleMutation.error}
              onSave={(permissionCodes, expectedRowVersion) => {
                if (!selectedRole) return
                updateRoleMutation.mutate({
                  id: selectedRole.id,
                  values: { permissions: permissionCodes, expectedRowVersion },
                })
              }}
              onReload={() => {
                updateRoleMutation.reset()
                void rolesQuery.refetch()
              }}
            />
          )}
        </div>
      )}

      {createdUser && (
        <TemporaryPasswordDialog createdUser={createdUser} onClose={() => setCreatedUser(null)} />
      )}
    </div>
  )
}
