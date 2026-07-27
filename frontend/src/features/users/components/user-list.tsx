import { SearchIcon } from '../../../shared/ui/icons'
import { pluralize } from '../../../shared/lib/formatters'
import type { User } from '../api/users-api'
import './user-list.css'

function getInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : ''
  return `${first}${last}`.toUpperCase()
}

interface UserListProps {
  users: User[]
  activeCount: number
  selectedId: string | null
  search: string
  isLoading: boolean
  onSearchChange: (value: string) => void
  onSelect: (id: string) => void
}

export function UserList({
  users,
  activeCount,
  selectedId,
  search,
  isLoading,
  onSearchChange,
  onSelect,
}: UserListProps) {
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

      <div className="user-list__header" role="presentation">
        <span>Usuário</span>
        <span>Perfil</span>
        <span>Status</span>
        <span aria-hidden="true" />
      </div>

      <div className="user-list__rows" role="list">
        {isLoading && <p className="user-list__empty">Carregando…</p>}
        {!isLoading && users.length === 0 && (
          <p className="user-list__empty">Nenhum usuário encontrado.</p>
        )}
        {users.map((user) => (
          <button
            key={user.id}
            type="button"
            role="listitem"
            className="user-list__row"
            data-selected={user.id === selectedId}
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
            <span className="user-list__role">{user.roleName}</span>
            <span className="user-list__status" data-active={user.isActive}>
              ● {user.isActive ? 'Ativo' : 'Inativo'}
            </span>
            <span aria-hidden="true" />
          </button>
        ))}
      </div>
    </div>
  )
}
