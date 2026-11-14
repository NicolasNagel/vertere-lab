import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
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
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/" element={<AppShell />}>
              <Route index element={<p>conteúdo dashboard</p>} />
              <Route path="/cadastros/clinicas" element={<p>conteúdo clínicas</p>} />
              <Route path="/operacao" element={<p>conteúdo operação</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

// Cada fase reinicia a árvore e os handlers do MSW para não herdar resposta da anterior.
function restart(view: ReturnType<typeof renderShell>) {
  view.unmount()
  server.resetHandlers()
}

test('keeps the main navigation visible on every route, shows the user footer and disables items without a route', async () => {
  const user = userEvent.setup()

  mockAuthenticatedUser()
  let view = renderShell('/cadastros/clinicas')
  expect(await screen.findByText('conteúdo clínicas')).toBeInTheDocument()
  expect(screen.getByLabelText('Navegação principal')).toBeInTheDocument()
  restart(view)

  mockAuthenticatedUser(['attendances.read'])
  view = renderShell('/operacao')
  expect(await screen.findByText('conteúdo operação')).toBeInTheDocument()
  expect(screen.getByLabelText('Navegação principal')).toBeInTheDocument()
  restart(view)

  mockAuthenticatedUser()
  renderShell('/')
  expect(await screen.findByText('conteúdo dashboard')).toBeInTheDocument()

  // Rodapé com nome, perfil e iniciais.
  expect(await screen.findByText('Fabianna Garcia')).toBeInTheDocument()
  expect(screen.getByText('Administradora')).toBeInTheDocument()
  expect(screen.getByText('FG')).toBeInTheDocument()

  // Item sem rota não é interativo.
  const laudos = screen.getByText('Laudos').closest('[aria-disabled]')
  expect(laudos).toHaveAttribute('aria-disabled', 'true')
  expect(laudos).toHaveAttribute('tabindex', '-1')
  expect(screen.queryByRole('link', { name: /laudos/i })).not.toBeInTheDocument()
  await user.click(screen.getByText('Laudos'))
  expect(screen.getByText('conteúdo dashboard')).toBeInTheDocument()
})

test('opens and closes the mobile navigation when a destination is selected', async () => {
  const user = userEvent.setup()
  mockAuthenticatedUser()
  renderShell('/')

  const menuButton = await screen.findByRole('button', {
    name: 'Abrir navegação',
  })
  expect(menuButton).toHaveAttribute('aria-expanded', 'false')

  await user.click(menuButton)
  expect(menuButton).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByRole('button', { name: 'Fechar navegação' })).toBeInTheDocument()

  await user.click(screen.getByRole('link', { name: /clínicas/i }))
  expect(await screen.findByText('conteúdo clínicas')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Abrir navegação' })).toHaveAttribute(
    'aria-expanded',
    'false',
  )
  expect(screen.queryByRole('button', { name: 'Fechar navegação' })).not.toBeInTheDocument()
})

test('shows "Usuários" only with the matching read permission', async () => {
  mockAuthenticatedUser(['clinics.manage'])
  const view = renderShell('/')
  await screen.findByText('conteúdo dashboard')
  expect(screen.queryByRole('link', { name: /^usuários$/i })).not.toBeInTheDocument()
  restart(view)

  mockAuthenticatedUser(['users.read'])
  renderShell('/')
  expect(await screen.findByRole('link', { name: /^usuários$/i })).toHaveAttribute(
    'href',
    '/administracao/usuarios',
  )
})
