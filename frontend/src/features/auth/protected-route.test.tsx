import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from './auth-provider'
import { ProtectedRoute } from './protected-route'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderProtected() {
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
            <Route path="/login" element={<p>tela de login</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('redirects to /login without a session and renders the content with a valid one', async () => {
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
  const view = renderProtected()
  expect(await screen.findByText('tela de login')).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  server.use(
    http.get('/api/v1/auth/me', () =>
      HttpResponse.json({
        user: { id: '1', email: 'a@b.com', full_name: 'A', role_id: 'r', role_name: 'LAB_ADMIN' },
        permissions: ['users.read'],
      }),
    ),
  )
  renderProtected()
  expect(await screen.findByText('conteúdo protegido')).toBeInTheDocument()
})
