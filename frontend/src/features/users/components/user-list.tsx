import { describeError } from '../../../shared/api/describe-error'
import { SearchIcon } from '../../../shared/ui/icons'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { Pagination } from '../../../shared/ui/pagination'
import { getInitials, pluralize } from '../../../shared/lib/formatters'
import type { SelectOption } from '../../../shared/ui/select'
import type { User } from '../api/users-api'
import { AssignRoleDialog } from './assign-role-dialog'
import './user-list.css'

// Cor da tag é só apresentação (não decide autorização por nome de papel) —
// perfis administrativos, de recepção, financeiro e técnicos/laboratoriais
// ganham a cor do grupo que representam, igual ao mockup de referência;
// qualquer papel fora dessa lista (perfil customizado, CLINIC_*) cai no
// neutro em vez de ficar sem cor.
function roleBadgeVariant(roleName: string): 'admin' | 'reception' | 'finance' | 'technical' | 'neutral' {
  switch (roleName) {
    case 'SUPER_ADMIN':
    case 'LAB_ADMIN':
      return 'admin'
    case 'RECEPTION':
      return 'reception'
    case 'FINANCE':
      return 'finance'
    case 'TECHNICAL':
    case 'TECHNICAL_MANAGER':
      return 'technical'
    default:
      return 'neutral'
  }
}

interface UserListProps {
  users: User[]
  activeCount: number
  selectedId: string | null
  search: string
  isLoading: boolean
  onSearchChange: (value: string) => void
  onSelect: (id: string) => void
  page?: number
  pageSize?: number
  total?: number
  onPageChange?: (page: number) => void
  canAssignRole: boolean
  canDeactivate: boolean
  canActivate: boolean
  roleOptions: SelectOption[]
  assigningRoleForId: string | null
  assignRoleSubmitting: boolean
  assignRoleError?: unknown
  statusChangeError?: unknown
  onStartAssignRole: (id: string) => void
  onCancelAssignRole: () => void
  onSubmitAssignRole: (id: string, roleId: string) => void
  onDeactivate: (id: string) => void
  onActivate: (id: string) => void
}

export function UserList({
  users,
  activeCount,
  selectedId,
  search,
  isLoading,
  onSearchChange,
  onSelect,
  page,
  pageSize,
  total,
  onPageChange,
  canAssignRole,
  canDeactivate,
  canActivate,
  roleOptions,
  assigningRoleForId,
  assignRoleSubmitting,
  assignRoleError,
  statusChangeError,
  onStartAssignRole,
  onCancelAssignRole,
  onSubmitAssignRole,
  onDeactivate,
  onActivate,
}: UserListProps) {
  const statusChangeErrorMessage = describeError(statusChangeError)
  return (
    <div className="user-list">
      <div className="user-list__search">
        <SearchIcon className="user-list__search-icon" />
        <input
          type="search"
          className="user-list__search-input"
          placeholder="Buscar usuário..."
          aria-label="Buscar usuário"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
        <span className="user-list__count">
          {activeCount} {pluralize(activeCount, 'ativo', 'ativos')}
        </span>
      </div>

      {statusChangeErrorMessage && (
        <p role="alert" className="user-list__domain-error">
          {statusChangeErrorMessage}
        </p>
      )}

      <div className="user-list__header" role="presentation">
        <span>Usuário</span>
        <span>Perfil</span>
        <span>Status</span>
        <span aria-hidden="true" />
      </div>

      <div className="user-list__rows">
        {isLoading && <p className="user-list__empty">Carregando…</p>}
        {!isLoading && users.length === 0 && (
          <p className="user-list__empty">Nenhum usuário encontrado.</p>
        )}
        {users.map((user) => {
          const menuItems: KebabMenuItem[] = []
          if (canAssignRole) {
            menuItems.push({ label: 'Alterar perfil', onSelect: () => onStartAssignRole(user.id) })
          }
          if (user.isActive && canDeactivate) {
            menuItems.push({ label: 'Desativar', onSelect: () => onDeactivate(user.id), destructive: true })
          }
          if (!user.isActive && canActivate) {
            menuItems.push({ label: 'Reativar', onSelect: () => onActivate(user.id) })
          }
          const isAssigningRole = assigningRoleForId === user.id

          return (
            <div key={user.id} className="user-list__row" data-selected={user.id === selectedId}>
              <button
                type="button"
                className="user-list__row-select"
                onClick={() => onSelect(user.id)}
              >
                <div className="user-list__identity">
                  <span className="user-list__avatar" aria-hidden="true">
                    {getInitials(user.fullName)}
                  </span>
                  <div>
                    <div className="user-list__name">{user.fullName}</div>
                    <div className="user-list__email">{user.email}</div>
                  </div>
                </div>
                <span className="user-list__role" data-variant={roleBadgeVariant(user.roleName)}>
                  {user.roleName}
                </span>
                <span className="user-list__status" data-active={user.isActive}>
                  ● {user.isActive ? 'Ativo' : 'Inativo'}
                </span>
              </button>

              <div className="user-list__row-actions">
                {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}

                {isAssigningRole && (
                  <div className="user-list__row-popover">
                    <AssignRoleDialog
                      currentRoleId={user.roleId}
                      roleOptions={roleOptions}
                      submitting={assignRoleSubmitting}
                      error={assignRoleError}
                      onCancel={onCancelAssignRole}
                      onSubmit={(roleId) => onSubmitAssignRole(user.id, roleId)}
                    />
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
      {page && pageSize && total !== undefined && onPageChange && (
        <Pagination
          itemLabel={['usuário', 'usuários']}
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={onPageChange}
        />
      )}
    </div>
  )
}
