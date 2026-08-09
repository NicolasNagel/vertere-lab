import { ApiError, type ApiErrorBody } from '../../../shared/api/errors'

const API_BASE = '/api/v1'

export { ApiError }

export interface LoginPayload {
  login: string
  password: string
  rememberMe: boolean
}

export interface AuthenticatedUser {
  id: string
  email: string
  fullName: string
  roleId: string
  roleName: string
  roleScope: 'GLOBAL' | 'LAB' | 'CLINIC'
  clinicIds: string[]
  rowVersion: number
  permissions: string[]
}

interface ApiUser {
  id: string
  email: string
  full_name: string
  role_id: string
  role_name: string
  role_scope: 'GLOBAL' | 'LAB' | 'CLINIC'
  clinic_ids: string[]
  row_version: number
}

interface ApiAuthResponse {
  user: ApiUser
  permissions: string[]
}

async function parseAuthResponse(response: Response): Promise<AuthenticatedUser> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null
    throw new ApiError(
      response.status,
      body?.error?.code ?? 'UNKNOWN',
      body?.error?.message ?? 'Erro desconhecido.',
    )
  }
  const body = (await response.json()) as ApiAuthResponse
  return {
    id: body.user.id,
    email: body.user.email,
    fullName: body.user.full_name,
    roleId: body.user.role_id,
    roleName: body.user.role_name,
    roleScope: body.user.role_scope,
    clinicIds: body.user.clinic_ids,
    rowVersion: body.user.row_version,
    permissions: body.permissions,
  }
}

export async function login(payload: LoginPayload): Promise<AuthenticatedUser> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      login: payload.login,
      password: payload.password,
      remember_me: payload.rememberMe,
    }),
  })
  return parseAuthResponse(response)
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' })
}

export async function fetchMe(): Promise<AuthenticatedUser> {
  const response = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' })
  return parseAuthResponse(response)
}
