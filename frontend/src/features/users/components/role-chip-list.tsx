import { pluralize } from '../../../shared/lib/formatters'
import type { Role } from '../../roles/api/roles-api'
import './role-chip-list.css'

interface RoleChipListProps {
  roles: Role[]
  selectedRoleId: string | null
  canManageRoles: boolean
  onSelect: (roleId: string) => void
  onCreateRole: () => void
}

export function RoleChipList({
  roles,
  selectedRoleId,
  canManageRoles,
  onSelect,
  onCreateRole,
}: RoleChipListProps) {
  return (
    <div className="role-chip-list">
      <div className="role-chip-list__header">
        <span className="role-chip-list__count">
          Perfis de acesso · {roles.length} {pluralize(roles.length, 'perfil', 'perfis')}
        </span>
        {canManageRoles && (
          <button type="button" className="role-chip-list__new-link" onClick={onCreateRole}>
            + novo perfil
          </button>
        )}
      </div>
      <div className="role-chip-list__chips">
        {roles.map((role) => (
          <button
            key={role.id}
            type="button"
            className="role-chip-list__chip"
            data-selected={role.id === selectedRoleId}
            onClick={() => onSelect(role.id)}
          >
            {role.name}
          </button>
        ))}
      </div>
    </div>
  )
}
