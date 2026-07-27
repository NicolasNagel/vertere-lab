import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { UsersPage } from './users-page'

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

function rolesListHandler() {
  return http.get('/api/v1/permission-profiles', () =>
    HttpResponse.json({
      items: [
        {
          id: 'r2',
          name: 'RECEPTION',
          scope: 'LAB',
          description: '',
          is_system: true,
          permissions: [],
          row_version: 1,
        },
        {
          id: 'r3',
          name: 'FINANCE',
          scope: 'LAB',
          description: '',
          is_system: true,
          permissions: [],
          row_version: 1,
        },
      ],
      total: 2,
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

test('lists users returned by the API', async () => {
  server.use(meHandler(['users.read']), usersListHandler(), rolesListHandler())
  renderWithProviders(<UsersPage />)

  expect(await screen.findByText('Recepção Um')).toBeInTheDocument()
})

test('hides the "Novo usuário" action for a user without users.create', async () => {
  server.use(meHandler(['users.read']), usersListHandler(), rolesListHandler())
  renderWithProviders(<UsersPage />)

  await screen.findByText('Recepção Um')
  expect(screen.queryByRole('button', { name: /Novo usuário/i })).not.toBeInTheDocument()
})

test('shows the "Novo usuário" action for a user with users.create', async () => {
  server.use(meHandler(['users.read', 'users.create']), usersListHandler(), rolesListHandler())
  renderWithProviders(<UsersPage />)

  expect(await screen.findByRole('button', { name: /Novo usuário/i })).toBeInTheDocument()
})

test('creates a user and shows the one-time temporary password', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['users.read', 'users.create']),
    usersListHandler(),
    rolesListHandler(),
    http.post('/api/v1/users', () =>
      HttpResponse.json(
        {
          user: {
            id: 'u3',
            email: 'nova@vertere.local',
            full_name: 'Nova Pessoa',
            is_active: true,
            role_id: 'r2',
            role_name: 'RECEPTION',
            created_at: '2026-01-01T00:00:00Z',
          },
          temporary_password: 'sEnh4Temp0rar1a!',
        },
        { status: 201 },
      ),
    ),
  )
  renderWithProviders(<UsersPage />)

  await user.click(await screen.findByRole('button', { name: /Novo usuário/i }))
  await user.type(screen.getByLabelText('Nome completo'), 'Nova Pessoa')
  await user.type(screen.getByLabelText('E-mail'), 'nova@vertere.local')
  await user.selectOptions(screen.getByLabelText('Perfil'), 'r2')
  await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

  expect(await screen.findByText('sEnh4Temp0rar1a!')).toBeInTheDocument()
  expect(screen.getByText(/Nova Pessoa/)).toBeInTheDocument()
})

test('deactivates the selected user', async () => {
  const user = userEvent.setup()
  let isActive = true
  const targetUser = {
    id: 'u2',
    email: 'reception@vertere.local',
    full_name: 'Recepção Um',
    role_id: 'r2',
    role_name: 'RECEPTION',
    created_at: '2026-01-01T00:00:00Z',
  }
  server.use(
    meHandler(['users.read', 'users.deactivate']),
    http.get('/api/v1/users', () =>
      HttpResponse.json({
        items: [{ ...targetUser, is_active: isActive }],
        total: 1,
        page: 1,
        page_size: 100,
      }),
    ),
    rolesListHandler(),
    http.patch('/api/v1/users/u2/deactivate', () => {
      isActive = false
      return HttpResponse.json({ ...targetUser, is_active: isActive })
    }),
  )
  renderWithProviders(<UsersPage />)

  await user.click(await screen.findByText('Recepção Um'))
  await user.click(screen.getByRole('button', { name: 'Mais ações' }))
  await user.click(screen.getByRole('menuitem', { name: 'Desativar' }))

  await waitFor(() => expect(screen.getAllByText(/Inativo/).length).toBeGreaterThan(0))
})

test('shows the backend rejection message when deactivating would self-lockout, instead of failing silently', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['users.read', 'users.deactivate']),
    usersListHandler(),
    rolesListHandler(),
    http.patch('/api/v1/users/u2/deactivate', () =>
      HttpResponse.json(
        {
          error: {
            code: 'CONFLICT',
            message: 'Esta ação removeria o último usuário capaz de gerenciar usuários.',
            details: [],
          },
        },
        { status: 409 },
      ),
    ),
  )
  renderWithProviders(<UsersPage />)

  await user.click(await screen.findByText('Recepção Um'))
  await user.click(screen.getByRole('button', { name: 'Mais ações' }))
  await user.click(screen.getByRole('menuitem', { name: 'Desativar' }))

  expect(
    await screen.findByText('Esta ação removeria o último usuário capaz de gerenciar usuários.'),
  ).toBeInTheDocument()
})

test('shows the "sem permissão" message instead of an empty list when listing users is forbidden', async () => {
  server.use(
    meHandler(['clinics.read']),
    http.get('/api/v1/users', () =>
      HttpResponse.json(
        { error: { code: 'FORBIDDEN', message: 'Permissão ausente: users.read', details: [] } },
        { status: 403 },
      ),
    ),
    rolesListHandler(),
  )
  renderWithProviders(<UsersPage />)

  expect(
    await screen.findByText('Você não tem permissão para visualizar usuários.'),
  ).toBeInTheDocument()
  expect(screen.queryByText('Nenhum usuário encontrado.')).not.toBeInTheDocument()
})
