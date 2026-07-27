import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../features/auth/auth-provider'
import { AppShell } from './app-shell'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function mockAuthenticatedUser(permissions: string[] = ['clinics.manage']) {
  server.use(
    http.get('/api/v1/auth/me', () =>
      HttpResponse.json({
        user: {
          id: '1',
          email: 'fabianna@vertere.local',
          full_name: 'Fabianna Garcia',
          role_id: 'r',
          role_name: 'Administradora',
        },
        permissions,
      }),
    ),
  )
}

function renderShell(initialPath: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/" element={<AppShell />}>
              <Route index element={<p>conteúdo dashboard</p>} />
              <Route path="/cadastros/clinicas" element={<p>conteúdo clínicas</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('highlights the nav item matching the current route', async () => {
  mockAuthenticatedUser()
  renderShell('/cadastros/clinicas')

  expect(await screen.findByText('conteúdo clínicas')).toBeInTheDocument()

  const clinicsLink = screen.getByRole('link', { name: /clínicas/i })
  expect(clinicsLink).toHaveAttribute('aria-current', 'page')

  const dashboardLink = screen.getByRole('link', { name: /dashboard/i })
  expect(dashboardLink).not.toHaveAttribute('aria-current')
})

test('items without a route are not interactive', async () => {
  mockAuthenticatedUser()
  renderShell('/')

  expect(await screen.findByText('conteúdo dashboard')).toBeInTheDocument()

  const laudos = screen.getByText('Laudos').closest('[aria-disabled]')
  expect(laudos).toHaveAttribute('aria-disabled', 'true')
  expect(laudos).toHaveAttribute('tabindex', '-1')
  expect(screen.queryByRole('link', { name: /laudos/i })).not.toBeInTheDocument()

  const user = userEvent.setup()
  await user.click(screen.getByText('Laudos'))
  expect(screen.getByText('conteúdo dashboard')).toBeInTheDocument()
})

test('footer shows the authenticated user name, role and initials', async () => {
  mockAuthenticatedUser()
  renderShell('/')

  expect(await screen.findByText('Fabianna Garcia')).toBeInTheDocument()
  expect(screen.getByText('Administradora')).toBeInTheDocument()
  expect(screen.getByText('FG')).toBeInTheDocument()
})

test('hides "Usuários" and "Perfis de permissão" without the matching read permission', async () => {
  mockAuthenticatedUser(['clinics.manage'])
  renderShell('/')

  await screen.findByText('conteúdo dashboard')
  expect(screen.queryByRole('link', { name: /^usuários$/i })).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /perfis de permissão/i })).not.toBeInTheDocument()
})

test('shows "Usuários" and "Perfis de permissão" with users.read and roles.read', async () => {
  mockAuthenticatedUser(['users.read', 'roles.read'])
  renderShell('/')

  expect(await screen.findByRole('link', { name: /^usuários$/i })).toHaveAttribute(
    'href',
    '/administracao/usuarios',
  )
  expect(screen.getByRole('link', { name: /perfis de permissão/i })).toHaveAttribute(
    'href',
    '/administracao/perfis',
  )
})
