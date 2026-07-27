import { throwIfNotOk } from '../../../shared/api/errors'

const API_BASE = '/api/v1'

export interface User {
  id: string
  email: string
  fullName: string
  isActive: boolean
  roleId: string
  roleName: string
  createdAt: string
}

export interface UserPage {
  items: User[]
  total: number
  page: number
  pageSize: number
}

export interface UserListParams {
  search?: string
  isActive?: boolean
  page?: number
  pageSize?: number
}

export interface CreateUserValues {
  email: string
  fullName: string
  roleId: string
}

export interface CreatedUser {
  user: User
  temporaryPassword: string
}

interface ApiUser {
  id: string
  email: string
  full_name: string
  is_active: boolean
  role_id: string
  role_name: string
  created_at: string
}

interface ApiUserPage {
  items: ApiUser[]
  total: number
  page: number
  page_size: number
}

interface ApiCreatedUser {
  user: ApiUser
  temporary_password: string
}

function fromApiUser(user: ApiUser): User {
  return {
    id: user.id,
    email: user.email,
    fullName: user.full_name,
    isActive: user.is_active,
    roleId: user.role_id,
    roleName: user.role_name,
    createdAt: user.created_at,
  }
}

export async function fetchUsers(params: UserListParams = {}): Promise<UserPage> {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.isActive !== undefined) query.set('is_active', String(params.isActive))
  query.set('page', String(params.page ?? 1))
  query.set('page_size', String(params.pageSize ?? 100))

  const response = await fetch(`${API_BASE}/users?${query.toString()}`, {
    credentials: 'include',
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiUserPage
  return {
    items: body.items.map(fromApiUser),
    total: body.total,
    page: body.page,
    pageSize: body.page_size,
  }
}

export async function createUser(values: CreateUserValues): Promise<CreatedUser> {
  const response = await fetch(`${API_BASE}/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      email: values.email,
      full_name: values.fullName,
      role_id: values.roleId,
    }),
  })
  await throwIfNotOk(response)
  const body = (await response.json()) as ApiCreatedUser
  return { user: fromApiUser(body.user), temporaryPassword: body.temporary_password }
}

export async function assignUserRole(id: string, roleId: string): Promise<User> {
  const response = await fetch(`${API_BASE}/users/${id}/role`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ role_id: roleId }),
  })
  await throwIfNotOk(response)
  return fromApiUser((await response.json()) as ApiUser)
}

export async function deactivateUser(id: string): Promise<User> {
  const response = await fetch(`${API_BASE}/users/${id}/deactivate`, {
    method: 'PATCH',
    credentials: 'include',
  })
  await throwIfNotOk(response)
  return fromApiUser((await response.json()) as ApiUser)
}

export async function activateUser(id: string): Promise<User> {
  const response = await fetch(`${API_BASE}/users/${id}/activate`, {
    method: 'PATCH',
    credentials: 'include',
  })
  await throwIfNotOk(response)
  return fromApiUser((await response.json()) as ApiUser)
}
