import { describeError } from '../../../shared/api/describe-error'
import { Button } from '../../../shared/ui/button'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import type { SelectOption } from '../../../shared/ui/select'
import type { User } from '../api/users-api'
import { AssignRoleDialog } from './assign-role-dialog'
import './user-detail.css'

interface UserDetailProps {
  user: User | null
  isLoading: boolean
  isAssigningRole: boolean
  canAssignRole: boolean
  canDeactivate: boolean
  canActivate: boolean
  roleOptions: SelectOption[]
  assignRoleSubmitting: boolean
  assignRoleError?: unknown
  statusChangeError?: unknown
  onStartAssignRole: () => void
  onCancelAssignRole: () => void
  onSubmitAssignRole: (roleId: string) => void
  onDeactivate: () => void
  onActivate: () => void
}

export function UserDetail({
  user,
  isLoading,
  isAssigningRole,
  canAssignRole,
  canDeactivate,
  canActivate,
  roleOptions,
  assignRoleSubmitting,
  assignRoleError,
  statusChangeError,
  onStartAssignRole,
  onCancelAssignRole,
  onSubmitAssignRole,
  onDeactivate,
  onActivate,
}: UserDetailProps) {
  if (isLoading) {
    return (
      <div className="user-detail">
        <p className="user-detail__empty">Carregando…</p>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="user-detail">
        <p className="user-detail__empty">Selecione um usuário na lista ao lado.</p>
      </div>
    )
  }

  const menuItems: KebabMenuItem[] = []
  if (user.isActive && canDeactivate) {
    menuItems.push({ label: 'Desativar', onSelect: onDeactivate, destructive: true })
  }
  if (!user.isActive && canActivate) {
    menuItems.push({ label: 'Reativar', onSelect: onActivate })
  }

  const statusChangeErrorMessage = describeError(statusChangeError)

  return (
    <div className="user-detail">
      <div className="user-detail__header">
        <div>
          <div className="user-detail__title-row">
            <h2 className="user-detail__title">{user.fullName}</h2>
            <span className="user-detail__status" data-active={user.isActive}>
              ● {user.isActive ? 'Ativo' : 'Inativo'}
            </span>
          </div>
          <p className="user-detail__email">{user.email}</p>
        </div>
        <div className="user-detail__actions">
          {canAssignRole && !isAssigningRole && (
            <Button type="button" variant="ghost" onClick={onStartAssignRole}>
              Alterar perfil
            </Button>
          )}
          {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}
        </div>
      </div>

      <dl className="user-detail__fields">
        <dt>Perfil</dt>
        <dd>{user.roleName}</dd>
        <dt>Criado em</dt>
        <dd>{new Date(user.createdAt).toLocaleDateString('pt-BR')}</dd>
      </dl>

      {statusChangeErrorMessage && (
        <p role="alert" className="user-detail__domain-error">
          {statusChangeErrorMessage}
        </p>
      )}

      {isAssigningRole && (
        <AssignRoleDialog
          currentRoleId={user.roleId}
          roleOptions={roleOptions}
          submitting={assignRoleSubmitting}
          error={assignRoleError}
          onCancel={onCancelAssignRole}
          onSubmit={onSubmitAssignRole}
        />
      )}
    </div>
  )
}
