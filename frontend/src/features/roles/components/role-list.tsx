import { pluralize } from '../../../shared/lib/formatters'
import type { Role } from '../api/roles-api'
import './role-list.css'

const SCOPE_LABELS: Record<Role['scope'], string> = {
  GLOBAL: 'Global',
  LAB: 'Laboratório',
  CLINIC: 'Clínica',
}

interface RoleListProps {
  roles: Role[]
  selectedId: string | null
  isLoading: boolean
  onSelect: (id: string) => void
}

export function RoleList({ roles, selectedId, isLoading, onSelect }: RoleListProps) {
  return (
    <div className="role-list">
      <div className="role-list__header-bar">
        <span className="role-list__count">
          {roles.length} {pluralize(roles.length, 'perfil', 'perfis')}
        </span>
      </div>

      <div className="role-list__rows" role="list">
        {isLoading && <p className="role-list__empty">Carregando…</p>}
        {!isLoading && roles.length === 0 && (
          <p className="role-list__empty">Nenhum perfil encontrado.</p>
        )}
        {roles.map((role) => (
          <button
            key={role.id}
            type="button"
            role="listitem"
            className="role-list__row"
            data-selected={role.id === selectedId}
            onClick={() => onSelect(role.id)}
          >
            <div className="role-list__row-header">
              <span className="role-list__row-name">{role.name}</span>
              <span className="role-list__row-scope">{SCOPE_LABELS[role.scope]}</span>
            </div>
            <div className="role-list__row-meta">
              {role.permissions.length} {pluralize(role.permissions.length, 'permissão', 'permissões')}
              {role.isSystem ? ' · Definido pelo sistema' : ''}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
