import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { RolesPage } from './roles-page'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function meHandler(permissions: string[]) {
  return http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      user: { id: 'u1', email: 'admin@vertere.local', full_name: 'Admin', role_id: 'r1', role_name: 'LAB_ADMIN' },
      permissions,
    }),
  )
}

const receptionRole = {
  id: 'r2',
  name: 'RECEPTION',
  scope: 'LAB',
  description: 'Cadastros e atendimentos.',
  is_system: true,
  permissions: ['clinics.read', 'patients.read'],
  row_version: 1,
}

function rolesListHandler(roles: typeof receptionRole[] = [receptionRole]) {
  return http.get('/api/v1/permission-profiles', () =>
    HttpResponse.json({ items: roles, total: roles.length, page: 1, page_size: 100 }),
  )
}

function permissionsHandler() {
  return http.get('/api/v1/permissions', () =>
    HttpResponse.json([
      { id: 'p1', code: 'clinics.read', description: 'Ver clínicas' },
      { id: 'p2', code: 'clinics.manage', description: 'Editar clínicas' },
      { id: 'p3', code: 'patients.read', description: 'Ver pacientes' },
    ]),
  )
}

function usersListHandler() {
  return http.get('/api/v1/users', () =>
    HttpResponse.json({
      items: [
        {
          id: 'u2',
          email: 'reception@vertere.local',
          full_name: 'Recepção Um',
          is_active: true,
          role_id: 'r2',
          role_name: 'RECEPTION',
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    }),
  )
}

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>,
  )
}

test('lists permission profiles returned by the API', async () => {
  server.use(meHandler(['roles.read']), rolesListHandler(), permissionsHandler(), usersListHandler())
  renderWithProviders(<RolesPage />)

  expect(await screen.findByText('RECEPTION')).toBeInTheDocument()
})

test('hides the "Novo perfil" action for a user without roles.manage', async () => {
  server.use(meHandler(['roles.read']), rolesListHandler(), permissionsHandler(), usersListHandler())
  renderWithProviders(<RolesPage />)

  await screen.findByText('RECEPTION')
  expect(screen.queryByRole('button', { name: /Novo perfil/i })).not.toBeInTheDocument()
})

test('selecting a profile shows its permissions grouped by resource', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['roles.read', 'roles.manage']),
    rolesListHandler(),
    permissionsHandler(),
    usersListHandler(),
  )
  renderWithProviders(<RolesPage />)

  await user.click(await screen.findByText('RECEPTION'))

  expect(await screen.findByText('Perfil RECEPTION')).toBeInTheDocument()
  expect(screen.getByText('Clínicas')).toBeInTheDocument()
  expect(screen.getByText('Pacientes')).toBeInTheDocument()
  expect(screen.getByText(/aplicado a 1 usuário/)).toBeInTheDocument()
})

test('saves permission changes for a profile', async () => {
  const user = userEvent.setup()
  // O GET precisa refletir o resultado do PATCH depois da invalidação da
  // query — um mock estático faria o React Query manter a mesma referência
  // de objeto (structural sharing) e o painel nunca re-sincronizaria.
  let currentRole = receptionRole
  server.use(
    meHandler(['roles.read', 'roles.manage']),
    http.get('/api/v1/permission-profiles', () =>
      HttpResponse.json({ items: [currentRole], total: 1, page: 1, page_size: 100 }),
    ),
    permissionsHandler(),
    usersListHandler(),
    http.patch('/api/v1/permission-profiles/r2', () => {
      currentRole = {
        ...receptionRole,
        permissions: ['clinics.read', 'clinics.manage', 'patients.read'],
        row_version: 2,
      }
      return HttpResponse.json(currentRole)
    }),
  )
  renderWithProviders(<RolesPage />)

  await user.click(await screen.findByText('RECEPTION'))
  await screen.findByText('Perfil RECEPTION')

  await user.click(screen.getByLabelText('clinics.manage'))
  await user.click(screen.getByRole('button', { name: 'Salvar permissões' }))

  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Salvar permissões' })).toBeDisabled(),
  )
})

test('creates a new permission profile', async () => {
  const user = userEvent.setup()
  const auditorRole = {
    id: 'r9',
    name: 'AUDITOR',
    scope: 'LAB',
    description: '',
    is_system: false,
    permissions: ['clinics.read'],
    row_version: 1,
  }
  // O GET precisa incluir o perfil recém-criado depois da invalidação da
  // query, senão o painel de detalhe não encontra `selectedId` na lista.
  let roles = [receptionRole]
  server.use(
    meHandler(['roles.read', 'roles.manage']),
    http.get('/api/v1/permission-profiles', () =>
      HttpResponse.json({ items: roles, total: roles.length, page: 1, page_size: 100 }),
    ),
    permissionsHandler(),
    usersListHandler(),
    http.post('/api/v1/permission-profiles', () => {
      roles = [...roles, auditorRole]
      return HttpResponse.json(auditorRole, { status: 201 })
    }),
  )
  renderWithProviders(<RolesPage />)

  await user.click(await screen.findByRole('button', { name: /Novo perfil/i }))
  await user.type(screen.getByLabelText('Nome do perfil'), 'AUDITOR')
  await user.click(screen.getByLabelText('clinics.read'))
  await user.click(screen.getByRole('button', { name: 'Criar perfil' }))

  expect(await screen.findByText('Perfil AUDITOR')).toBeInTheDocument()
})

test('shows the "sem permissão" message instead of an empty list when listing profiles is forbidden', async () => {
  server.use(
    meHandler(['clinics.read']),
    http.get('/api/v1/permission-profiles', () =>
      HttpResponse.json(
        { error: { code: 'FORBIDDEN', message: 'Permissão ausente: roles.read', details: [] } },
        { status: 403 },
      ),
    ),
    permissionsHandler(),
    usersListHandler(),
  )
  renderWithProviders(<RolesPage />)

  expect(
    await screen.findByText('Você não tem permissão para visualizar perfis de permissão.'),
  ).toBeInTheDocument()
  expect(screen.queryByText('Nenhum perfil encontrado.')).not.toBeInTheDocument()
})
