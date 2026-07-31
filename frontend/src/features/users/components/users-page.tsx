import { useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { PlusIcon } from '../../../shared/ui/icons'
import type { SelectOption } from '../../../shared/ui/select'
import { useAuth } from '../../auth/auth-context'
import { useAllRolesQuery } from '../../roles/api/use-roles-query'
import { useActivateUserMutation } from '../api/use-activate-user-mutation'
import { useAssignRoleMutation } from '../api/use-assign-role-mutation'
import { useCreateUserMutation } from '../api/use-create-user-mutation'
import { useDeactivateUserMutation } from '../api/use-deactivate-user-mutation'
import { useUsersQuery } from '../api/use-users-query'
import type { CreatedUser } from '../api/users-api'
import { TemporaryPasswordDialog } from './temporary-password-dialog'
import { UserDetail } from './user-detail'
import { UserForm } from './user-form'
import { UserList } from './user-list'
import './users-page.css'

type PanelMode = 'view' | 'create'

export function UsersPage() {
  const { user } = useAuth()
  const canCreate = user?.permissions.includes('users.create') ?? false
  const canAssignRole = user?.permissions.includes('roles.assign') ?? false
  const canDeactivate = user?.permissions.includes('users.deactivate') ?? false
  const canActivate = user?.permissions.includes('users.activate') ?? false

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<PanelMode>('view')
  const [isAssigningRole, setIsAssigningRole] = useState(false)
  const [createdUser, setCreatedUser] = useState<CreatedUser | null>(null)

  const listQuery = useUsersQuery({ search: search || undefined, page, pageSize: 25 })
  // Fase 2 ainda não tem `ClinicMembership` real: perfis de escopo CLINIC
  // (CLINIC_ADMIN/VETERINARIAN/CLINIC_STAFF) não têm permissão nem vínculo
  // funcional, então ficam fora da lista de perfis atribuíveis aqui.
  const rolesQuery = useAllRolesQuery()

  const createMutation = useCreateUserMutation()
  const assignRoleMutation = useAssignRoleMutation()
  const deactivateMutation = useDeactivateUserMutation()
  const activateMutation = useActivateUserMutation()

  const users = listQuery.data?.items ?? []
  const activeCount = users.filter((item) => item.isActive).length
  const selectedUser = users.find((item) => item.id === selectedId) ?? null

  const roleOptions: SelectOption[] = (rolesQuery.data?.items ?? [])
    .filter((role) => role.scope !== 'CLINIC')
    .map((role) => ({ value: role.id, label: role.name }))

  const isForbidden = listQuery.error instanceof ApiError && listQuery.error.status === 403

  function handleSelect(id: string) {
    setSelectedId(id)
    setMode('view')
    setIsAssigningRole(false)
    deactivateMutation.reset()
    activateMutation.reset()
  }

  function handleStartCreate() {
    setSelectedId(null)
    setMode('create')
    setIsAssigningRole(false)
    deactivateMutation.reset()
    activateMutation.reset()
  }

  function handleDeactivate() {
    if (!selectedId) return
    deactivateMutation.mutate(selectedId)
  }

  function handleActivate() {
    if (!selectedId) return
    activateMutation.mutate(selectedId)
  }

  return (
    <div className="users-page">
      <div className="users-page__header">
        <div>
          <div className="users-page__eyebrow">Administração</div>
          <h1 className="users-page__title">Usuários & Permissões</h1>
        </div>
        {canCreate && (
          <Button type="button" className="users-page__new-button" onClick={handleStartCreate}>
            <PlusIcon /> Novo usuário
          </Button>
        )}
      </div>

      {isForbidden ? (
        <p className="users-page__forbidden">Você não tem permissão para visualizar usuários.</p>
      ) : (
        <div className="users-page__body">
          <UserList
            users={users}
            activeCount={activeCount}
            selectedId={mode === 'create' ? null : selectedId}
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
          />

          {mode === 'create' ? (
            <div className="users-page__create-panel">
              <h2 className="users-page__create-title">Novo usuário</h2>
              <UserForm
                roleOptions={roleOptions}
                submitting={createMutation.isPending}
                error={createMutation.error}
                onCancel={() => setMode('view')}
                onSubmit={(values) =>
                  createMutation.mutate(values, {
                    onSuccess: (created) => {
                      setCreatedUser(created)
                      setSelectedId(created.user.id)
                      setMode('view')
                    },
                  })
                }
              />
            </div>
          ) : (
            <UserDetail
              user={selectedUser}
              isLoading={selectedId !== null && listQuery.isLoading}
              isAssigningRole={isAssigningRole}
              canAssignRole={canAssignRole}
              canDeactivate={canDeactivate}
              canActivate={canActivate}
              roleOptions={roleOptions}
              assignRoleSubmitting={assignRoleMutation.isPending}
              assignRoleError={assignRoleMutation.error}
              statusChangeError={deactivateMutation.error ?? activateMutation.error}
              onStartAssignRole={() => setIsAssigningRole(true)}
              onCancelAssignRole={() => setIsAssigningRole(false)}
              onSubmitAssignRole={(roleId) => {
                if (!selectedId) return
                assignRoleMutation.mutate(
                  { id: selectedId, roleId },
                  { onSuccess: () => setIsAssigningRole(false) },
                )
              }}
              onDeactivate={handleDeactivate}
              onActivate={handleActivate}
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
