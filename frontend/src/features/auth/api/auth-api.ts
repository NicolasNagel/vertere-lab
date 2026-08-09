import { ApiError } from '../../../shared/api/errors'
import type { AuthResponse as ApiAuthResponse } from '../../../shared/api/generated'
import { apiRequest } from '../../../shared/api/http-client'

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

type CompleteApiAuthResponse = Omit<ApiAuthResponse, 'user'> & {
  user: Required<ApiAuthResponse['user']>
}

function fromApiAuthResponse(body: CompleteApiAuthResponse): AuthenticatedUser {
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
  const body = await apiRequest<CompleteApiAuthResponse>('/auth/login', {
    method: 'POST',
    body: {
      login: payload.login,
      password: payload.password,
      remember_me: payload.rememberMe,
    },
  })
  return fromApiAuthResponse(body)
}

export async function logout(): Promise<void> {
  await apiRequest<void>('/auth/logout', { method: 'POST' })
}

export async function fetchMe(): Promise<AuthenticatedUser> {
  return fromApiAuthResponse(await apiRequest<CompleteApiAuthResponse>('/auth/me'))
}
