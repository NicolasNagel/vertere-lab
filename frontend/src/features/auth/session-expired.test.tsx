import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
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
        { error: { code: 'UNAUTHENTICATED', message: 'Sessão expirada.', request_id: 'r', details: [] } },
        { status: 401 },
      ),
    ),
  )
}

test('shows a session-expired notice only when the user had an active session before', async () => {
  markSessionActive()
  mockUnauthenticated()

  renderApp()

  expect(await screen.findByText('Sua sessão expirou. Faça login novamente.')).toBeInTheDocument()
})

test('does not show a session-expired notice for a plain first visit', async () => {
  mockUnauthenticated()

  renderApp()

  await screen.findByRole('button', { name: 'Entrar no sistema' })
  expect(screen.queryByText('Sua sessão expirou. Faça login novamente.')).not.toBeInTheDocument()
})
