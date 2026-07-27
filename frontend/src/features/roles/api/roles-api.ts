import { throwIfNotOk } from '../../../shared/api/errors'

const API_BASE = '/api/v1'

export type RoleScope = 'GLOBAL' | 'LAB' | 'CLINIC'

export interface Role {
  id: string
  name: string
  scope: RoleScope
  description: string
  isSystem: boolean
  permissions: string[]
  rowVersion: number
}

export interface RolePage {
  items: Role[]
  total: number
  page: number
  pageSize: number
}

export interface RoleListParams {
  page?: number
  pageSize?: number
}

export interface CreateRoleValues {
  name: string
  scope: RoleScope
  description: string
  permissions: string[]
}

export interface UpdateRoleValues {
  permissions: string[]
  expectedRowVersion: number
}

export interface Permission {
  id: string
  code: string
  description: string
}

interface ApiRole {
  id: string
  name: string
  scope: RoleScope
  description: string
  is_system: boolean
  permissions: string[]
  row_version: number
}

interface ApiRolePage {
  items: ApiRole[]
  total: number
  page: number
  page_size: number
}

interface ApiPermission {
  id: string
  code: string
  description: string
}

function fromApiRole(role: ApiRole): Role {
  return {
    id: role.id,
    name: role.name,
    scope: role.scope,
    description: role.description,
    isSystem: role.is_system,
    permissions: role.permissions,
    rowVersion: role.row_version,
  }
}

function fromApiPermission(permission: ApiPermission): Permission {
  return { id: permission.id, code: permission.code, description: permission.description }
}

export async function fetchRoles(params: RoleListParams = {}): Promise<RolePage> {
  const query = new URLSearchParams()
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 100))

  const response = await fetch(`${API_BASE}/permission-profiles?${query.toString()}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiRolePage
  return {
    items: body.items.map(fromApiRole),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function fetchRole(id: string): Promise<Role> {
  const response = await fetch(`${API_BASE}/permission-profiles/${id}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  return fromApiRole((await response.json()) as ApiRole)
}

export async function createRole(values: CreateRoleValues): Promise<Role> {
  const response = await fetch(`${API_BASE}/permission-profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      name: values.name,
      scope: values.scope,
      description: values.description,
      permissions: values.permissions,
    }),
  })
  await throwIfNotOk(response)
  return fromApiRole((await response.json()) as ApiRole)
}

export async function updateRole(id: string, values: UpdateRoleValues): Promise<Role> {
  const response = await fetch(`${API_BASE}/permission-profiles/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      permissions: values.permissions,
      expected_row_version: values.expectedRowVersion,
    }),
  })
  await throwIfNotOk(response)
  return fromApiRole((await response.json()) as ApiRole)
}

export async function fetchPermissions(): Promise<Permission[]> {
  const response = await fetch(`${API_BASE}/permissions`, { credentials: 'include' })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiPermission[]
  return body.map(fromApiPermission)
}
