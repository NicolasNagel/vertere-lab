import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, beforeEach, expect, test } from 'vitest'

import { LoginPage } from './components/login-page'
import { AuthProvider } from './auth-provider'
import { ProtectedRoute } from './protected-route'
import { markSessionActive } from './session-flag'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
beforeEach(() => sessionStorage.clear())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <p>conteúdo protegido</p>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<LoginPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

function mockUnauthenticated() {
  server.use(
    http.get('/api/v1/auth/me', () =>
      HttpResponse.json(
        {
          error: {
            code: 'UNAUTHENTICATED',
            message: 'Sessão expirada.',
            request_id: 'r',
            details: [],
          },
        },
        { status: 401 },
      ),
    ),
  )
}

test('shows the session-expired notice only after an active session, and leaves /login after a successful login', async () => {
  const user = userEvent.setup()

  // Havia sessão ativa antes: avisa que expirou.
  markSessionActive()
  mockUnauthenticated()
  let view = renderApp()
  expect(await screen.findByText('Sua sessão expirou. Faça login novamente.')).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()
  sessionStorage.clear()

  // Primeira visita: sem aviso.
  mockUnauthenticated()
  view = renderApp()
  await screen.findByRole('button', { name: 'Entrar no sistema' })
  expect(screen.queryByText('Sua sessão expirou. Faça login novamente.')).not.toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  // Login bem-sucedido sai da rota /login.
  mockUnauthenticated()
  server.use(
    http.post('/api/v1/auth/login', () =>
      HttpResponse.json({
        user: {
          id: 'user-1',
          email: 'admin@qa.local',
          full_name: 'QA Admin',
          role_id: 'role-1',
          role_name: 'SUPER_ADMIN',
          role_scope: 'GLOBAL',
          clinic_ids: [],
          row_version: 1,
        },
        permissions: [],
      }),
    ),
  )
  renderApp()
  await user.type(await screen.findByLabelText('Usuário'), 'admin@qa.local')
  await user.type(screen.getByLabelText('Senha'), 'correct-password')
  await user.click(screen.getByRole('button', { name: 'Entrar no sistema' }))
  expect(await screen.findByText('conteúdo protegido')).toBeInTheDocument()
})
