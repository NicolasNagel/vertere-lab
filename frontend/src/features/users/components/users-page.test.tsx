import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { UsersPage } from './users-page'
import { pickOption } from '../../../test/dropdown'

const server = setupServer(clinicsHandler())

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function meHandler(permissions: string[]) {
  return http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      user: {
        id: 'u1',
        email: 'admin@vertere.local',
        full_name: 'Admin',
        role_id: 'r1',
        role_name: 'LAB_ADMIN',
      },
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

const receptionRole = {
  id: 'r2',
  name: 'RECEPTION',
  scope: 'LAB',
  description: 'Cadastros e atendimentos.',
  is_system: true,
  permissions: ['clinics.read', 'patients.read'],
  row_version: 1,
}

function rolesListHandler(roles: (typeof receptionRole)[] = [receptionRole]) {
  return http.get('/api/v1/permission-profiles', () =>
    HttpResponse.json({
      items: roles,
      total: roles.length,
      page: 1,
      page_size: 100,
    }),
  )
}

function permissionsHandler() {
  return http.get('/api/v1/permissions', () =>
    HttpResponse.json([
      {
        id: 'p1',
        code: 'clinics.read',
        description: 'Ver clínicas',
        master_only: false,
      },
      {
        id: 'p2',
        code: 'clinics.manage',
        description: 'Editar clínicas',
        master_only: false,
      },
      {
        id: 'p3',
        code: 'patients.read',
        description: 'Ver pacientes',
        master_only: false,
      },
      {
        id: 'p4',
        code: 'attendances.view_prices',
        description: 'Ver preço ao montar atendimento',
        master_only: true,
      },
    ]),
  )
}

function clinicsHandler() {
  return http.get('/api/v1/clinics', () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
  )
}

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>,
  )
}

// Cada fase reinicia a árvore e os handlers do MSW para não herdar resposta da anterior.
function restart(view: ReturnType<typeof renderWithProviders>) {
  view.unmount()
  server.resetHandlers()
}

const financeRole = {
  id: 'r3',
  name: 'FINANCE',
  scope: 'LAB',
  description: 'Preços e fechamentos.',
  is_system: true,
  permissions: ['clinics.read'],
  row_version: 1,
}

test('lists users and shows each action only to the permission that unlocks it', async () => {
  const user = userEvent.setup()
  const common = [usersListHandler(), rolesListHandler(), permissionsHandler()]

  // Só leitura: lista, sem "Novo usuário" nem "Novo perfil".
  server.use(meHandler(['users.read']), ...common)
  let view = renderWithProviders(<UsersPage />)
  expect(await screen.findByText('Recepção Um')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Novo usuário/i })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Novo perfil/i })).not.toBeInTheDocument()
  restart(view)

  // users.create libera "Novo usuário", mas não "Novo perfil".
  server.use(meHandler(['users.read', 'users.create']), ...common)
  view = renderWithProviders(<UsersPage />)
  expect(await screen.findByRole('button', { name: /Novo usuário/i })).toBeInTheDocument()
  await screen.findByText('Recepção Um')
  expect(screen.queryByRole('button', { name: /Novo perfil/i })).not.toBeInTheDocument()
  restart(view)

  // roles.manage libera "+ novo perfil" ao lado dos chips.
  server.use(meHandler(['users.read', 'roles.manage']), ...common)
  view = renderWithProviders(<UsersPage />)
  await user.click(await screen.findByRole('button', { name: '+ novo perfil' }))
  expect(await screen.findByRole('button', { name: 'Criar perfil' })).toBeInTheDocument()
  restart(view)

  // 403 na listagem mostra "sem permissão", não uma lista vazia.
  server.use(
    meHandler(['clinics.read']),
    http.get('/api/v1/users', () =>
      HttpResponse.json(
        {
          error: {
            code: 'FORBIDDEN',
            message: 'Permissão ausente: users.read',
            details: [],
          },
        },
        { status: 403 },
      ),
    ),
    rolesListHandler(),
    permissionsHandler(),
  )
  renderWithProviders(<UsersPage />)
  expect(
    await screen.findByText('Você não tem permissão para visualizar usuários.'),
  ).toBeInTheDocument()
  expect(screen.queryByText('Nenhum usuário encontrado.')).not.toBeInTheDocument()
})

test('selecting a user shows the grouped permissions of the role, with master-only locked, and chips do not move the selection', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['users.read', 'roles.manage']),
    usersListHandler(),
    rolesListHandler([receptionRole, financeRole]),
    permissionsHandler(),
  )
  renderWithProviders(<UsersPage />)

  // Seleção inicial: usuário Recepção Um → perfil RECEPTION, permissões por categoria.
  expect(await screen.findByText('Perfil RECEPTION')).toBeInTheDocument()
  expect(screen.getByText('Cadastros')).toBeInTheDocument()
  expect(screen.getByText('Operação')).toBeInTheDocument()
  expect(screen.queryByText('Financeiro')).not.toBeInTheDocument()
  expect(screen.getByText('Ver clínicas')).toBeInTheDocument()
  expect(screen.getByText('Ver pacientes')).toBeInTheDocument()
  expect(screen.getByText(/aplicado a 1 usuário/)).toBeInTheDocument()

  // Permissão exclusiva do Master fica travada num perfil que não é Master.
  const toggle = screen.getByLabelText('Ver preço ao montar atendimento')
  expect(toggle).toBeDisabled()
  expect(toggle).not.toBeChecked()
  expect(screen.getByText('Definido pelo Master')).toBeInTheDocument()

  // Clicar no chip de outro perfil não mexe na linha do usuário.
  const userRow = screen.getByText('Recepção Um').closest('[data-selected]')
  expect(userRow).toHaveAttribute('data-selected', 'true')
  await user.click(screen.getByRole('button', { name: 'FINANCE' }))
  expect(await screen.findByText('Perfil FINANCE')).toBeInTheDocument()
  expect(userRow).toHaveAttribute('data-selected', 'true')
})

test('saves permission changes and creates a profile, optionally cloned from another one', async () => {
  const user = userEvent.setup()
  // O GET precisa refletir o resultado das mutações depois da invalidação da
  // query — um mock estático faria o React Query manter a mesma referência
  // (structural sharing) e o painel nunca re-sincronizaria.
  let currentRole = receptionRole
  server.use(
    meHandler(['users.read', 'roles.manage']),
    usersListHandler(),
    http.get('/api/v1/permission-profiles', () =>
      HttpResponse.json({
        items: [currentRole],
        total: 1,
        page: 1,
        page_size: 100,
      }),
    ),
    permissionsHandler(),
    http.patch('/api/v1/permission-profiles/r2', () => {
      currentRole = {
        ...receptionRole,
        permissions: ['clinics.read', 'clinics.manage', 'patients.read'],
        row_version: 2,
      }
      return HttpResponse.json(currentRole)
    }),
  )
  let view = renderWithProviders(<UsersPage />)

  await screen.findByText('Perfil RECEPTION')
  await user.click(screen.getByLabelText('Editar clínicas'))
  await user.click(screen.getByRole('button', { name: 'Salvar permissões' }))
  await waitFor(() =>
    expect(screen.queryByRole('button', { name: 'Salvar permissões' })).toBeDisabled(),
  )
  restart(view)

  const auditorRole = {
    id: 'r9',
    name: 'AUDITOR',
    scope: 'LAB',
    description: '',
    is_system: false,
    permissions: ['clinics.read'],
    row_version: 1,
  }
  let roles = [receptionRole]
  server.use(
    meHandler(['users.read', 'roles.manage']),
    usersListHandler(),
    http.get('/api/v1/permission-profiles', () =>
      HttpResponse.json({
        items: roles,
        total: roles.length,
        page: 1,
        page_size: 100,
      }),
    ),
    permissionsHandler(),
    http.post('/api/v1/permission-profiles', () => {
      roles = [...roles, auditorRole]
      return HttpResponse.json(auditorRole, { status: 201 })
    }),
  )
  view = renderWithProviders(<UsersPage />)

  await user.click(await screen.findByRole('button', { name: /Novo perfil/i }))

  // Novo perfil é sempre escopo LAB: a permissão exclusiva do Master vem travada.
  expect(screen.getByLabelText('Ver preço ao montar atendimento')).toBeDisabled()
  expect(screen.getByText('Definido pelo Master')).toBeInTheDocument()

  // "Baseado em" clona as permissões do perfil base; "Começar do zero" limpa.
  expect(screen.getByLabelText('Editar clínicas')).not.toBeChecked()
  await pickOption(user, 'Baseado em', 'RECEPTION')
  expect(screen.getByLabelText('Ver clínicas')).toBeChecked()
  expect(screen.getByLabelText('Ver pacientes')).toBeChecked()
  expect(screen.getByLabelText('Editar clínicas')).not.toBeChecked()
  await pickOption(user, 'Baseado em', 'Começar do zero')
  expect(screen.getByLabelText('Ver clínicas')).not.toBeChecked()
  expect(screen.getByLabelText('Ver pacientes')).not.toBeChecked()

  await user.type(screen.getByLabelText('Nome do perfil'), 'AUDITOR')
  await user.click(screen.getByLabelText('Ver clínicas'))
  await user.click(screen.getByRole('button', { name: 'Criar perfil' }))
  expect(await screen.findByText('Perfil RECEPTION')).toBeInTheDocument()
})

test('creates users and shows the one-time temporary password, sending clinic memberships for CLINIC roles', async () => {
  const user = userEvent.setup()
  const createdUser = {
    id: 'u3',
    email: 'nova@vertere.local',
    full_name: 'Nova Pessoa',
    is_active: true,
    role_id: 'r2',
    role_name: 'RECEPTION',
    created_at: '2026-01-01T00:00:00Z',
  }
  server.use(
    meHandler(['users.read', 'users.create']),
    usersListHandler(),
    rolesListHandler(),
    permissionsHandler(),
    http.post('/api/v1/users', () =>
      HttpResponse.json(
        { user: createdUser, temporary_password: 'sEnh4Temp0rar1a!' },
        { status: 201 },
      ),
    ),
  )
  let view = renderWithProviders(<UsersPage />)

  await user.click(await screen.findByRole('button', { name: /Novo usuário/i }))
  await user.type(screen.getByLabelText('Nome completo'), 'Nova Pessoa')
  await user.type(screen.getByLabelText('E-mail'), 'nova@vertere.local')
  await pickOption(user, 'Perfil', 'RECEPTION')
  await user.click(screen.getByRole('button', { name: 'Criar usuário' }))
  expect(await screen.findByText('sEnh4Temp0rar1a!')).toBeInTheDocument()
  expect(screen.getByText(/Nova Pessoa/)).toBeInTheDocument()
  restart(view)

  let requestBody: Record<string, unknown> | null = null
  const clinicRole = {
    ...receptionRole,
    id: 'r-clinic',
    name: 'CLINIC_STAFF',
    scope: 'CLINIC',
  }
  server.use(
    meHandler(['users.read', 'users.create']),
    usersListHandler(),
    rolesListHandler([clinicRole]),
    permissionsHandler(),
    http.get('/api/v1/clinics', () =>
      HttpResponse.json({
        items: [{ id: 'c1', name: 'Clínica Central', status: 'ACTIVE' }],
        total: 1,
        page: 1,
        page_size: 100,
      }),
    ),
    http.post('/api/v1/users', async ({ request }) => {
      requestBody = (await request.json()) as Record<string, unknown>
      return HttpResponse.json(
        {
          user: {
            ...createdUser,
            id: 'u-clinic',
            email: 'clinic@vertere.local',
            full_name: 'Pessoa Clínica',
            role_id: 'r-clinic',
            role_name: 'CLINIC_STAFF',
            role_scope: 'CLINIC',
            clinic_ids: ['c1'],
            row_version: 1,
          },
          temporary_password: 'Temp1234!',
        },
        { status: 201 },
      )
    }),
  )
  view = renderWithProviders(<UsersPage />)

  await user.click(await screen.findByRole('button', { name: /Novo usuário/i }))
  await user.type(screen.getByLabelText('Nome completo'), 'Pessoa Clínica')
  await user.type(screen.getByLabelText('E-mail'), 'clinic@vertere.local')
  await pickOption(user, 'Perfil', 'CLINIC_STAFF')
  await user.click(screen.getByLabelText('Clínica Central'))
  await user.click(screen.getByRole('button', { name: 'Criar usuário' }))
  await screen.findByText('Temp1234!')
  expect(requestBody).toMatchObject({
    role_id: 'r-clinic',
    clinic_ids: ['c1'],
  })
})

test('deactivates a user from the row menu and surfaces the backend rejection instead of failing silently', async () => {
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
    permissionsHandler(),
    http.patch('/api/v1/users/u2/deactivate', () => {
      isActive = false
      return HttpResponse.json({ ...targetUser, is_active: isActive })
    }),
  )
  let view = renderWithProviders(<UsersPage />)

  await user.click(await screen.findByText('Recepção Um'))
  await user.click(screen.getByRole('button', { name: 'Mais ações' }))
  await user.click(screen.getByRole('menuitem', { name: 'Desativar' }))
  await waitFor(() => expect(screen.getAllByText(/Inativo/).length).toBeGreaterThan(0))
  restart(view)

  // Autotrava: o 409 do backend aparece na tela.
  server.use(
    meHandler(['users.read', 'users.deactivate']),
    usersListHandler(),
    rolesListHandler(),
    permissionsHandler(),
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
  view = renderWithProviders(<UsersPage />)

  await user.click(await screen.findByText('Recepção Um'))
  await user.click(screen.getByRole('button', { name: 'Mais ações' }))
  await user.click(screen.getByRole('menuitem', { name: 'Desativar' }))
  expect(
    await screen.findByText('Esta ação removeria o último usuário capaz de gerenciar usuários.'),
  ).toBeInTheDocument()
})
