import type { Permission } from '../api/roles-api'

// Rótulo por prefixo de recurso real do catálogo (backend/app/modules/identity/
// infrastructure/seed.py) — não usa as seções fictícias do mockup
// (Operação/Laudos/Relatórios não existem como permissão ainda).
const RESOURCE_LABELS: Record<string, string> = {
  users: 'Usuários',
  roles: 'Perfis de permissão',
  permissions: 'Permissões',
  clinics: 'Clínicas',
  veterinarians: 'Veterinários',
  owners: 'Proprietários',
  patients: 'Pacientes',
  catalog: 'Catálogo de exames',
  pricing: 'Preços',
  attendances: 'Atendimentos',
  closures: 'Fechamentos',
  audit: 'Auditoria',
  imports: 'Importações',
}

export interface PermissionGroup {
  resource: string
  label: string
  permissions: Permission[]
}

function resourceOf(code: string): string {
  return code.split('.')[0] ?? code
}

export function labelForResource(resource: string): string {
  return RESOURCE_LABELS[resource] ?? resource
}

export function groupPermissionsByResource(permissions: Permission[]): PermissionGroup[] {
  const byResource = new Map<string, Permission[]>()
  for (const permission of permissions) {
    const resource = resourceOf(permission.code)
    const group = byResource.get(resource)
    if (group) {
      group.push(permission)
    } else {
      byResource.set(resource, [permission])
    }
  }
  return Array.from(byResource.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([resource, items]) => ({
      resource,
      label: labelForResource(resource),
      permissions: items,
    }))
}
