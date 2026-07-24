import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { ClinicsPage } from './clinics-page'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function meHandler(permissions: string[]) {
  return http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      user: { id: 'u1', email: 'a@b.com', full_name: 'A', role_id: 'r1', role_name: 'LAB_ADMIN' },
      permissions,
    }),
  )
}

function clinicsListHandler() {
  return http.get('/api/v1/clinics', () =>
    HttpResponse.json({
      items: [
        {
          id: 'c1',
          name: 'Schweitzer',
          tax_id: '78977352000199',
          phone: null,
          email: null,
          status: 'ACTIVE',
          address_zip_code: null,
          address_street: null,
          address_number: null,
          address_neighborhood: null,
          address_city: null,
          address_state: null,
          address_complement: null,
          notes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
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

test('lists clinics returned by the API', async () => {
  server.use(meHandler(['clinics.read']), clinicsListHandler())
  renderWithProviders(<ClinicsPage />)

  expect(await screen.findByText('Schweitzer')).toBeInTheDocument()
})

test('formats the CNPJ with the standard mask instead of raw digits', async () => {
  server.use(meHandler(['clinics.read']), clinicsListHandler())
  renderWithProviders(<ClinicsPage />)

  expect(await screen.findByText('78.977.352/0001-99')).toBeInTheDocument()
  expect(screen.queryByText('78977352000199')).not.toBeInTheDocument()
})

test('uses the singular form when there is exactly one active clinic', async () => {
  server.use(meHandler(['clinics.read']), clinicsListHandler())
  renderWithProviders(<ClinicsPage />)

  await screen.findByText('Schweitzer')
  expect(screen.getByText('1 ativa')).toBeInTheDocument()
})

test('hides the "Nova clínica" action for a user without clinics.manage', async () => {
  server.use(meHandler(['clinics.read']), clinicsListHandler())
  renderWithProviders(<ClinicsPage />)

  await screen.findByText('Schweitzer')
  expect(screen.queryByRole('button', { name: /Nova clínica/i })).not.toBeInTheDocument()
})

test('shows the "Nova clínica" action for a user with clinics.manage', async () => {
  server.use(meHandler(['clinics.read', 'clinics.manage']), clinicsListHandler())
  renderWithProviders(<ClinicsPage />)

  expect(await screen.findByRole('button', { name: /Nova clínica/i })).toBeInTheDocument()
})

test('creates a clinic and returns to the detail view', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['clinics.read', 'clinics.manage']),
    clinicsListHandler(),
    http.post('/api/v1/clinics', () =>
      HttpResponse.json(
        {
          id: 'c2',
          name: 'Bicho Urbano',
          tax_id: null,
          phone: null,
          email: null,
          status: 'ACTIVE',
          address_zip_code: null,
          address_street: null,
          address_number: null,
          address_neighborhood: null,
          address_city: null,
          address_state: null,
          address_complement: null,
          notes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
        },
        { status: 201 },
      ),
    ),
    http.get('/api/v1/clinics/c2', () =>
      HttpResponse.json({
        id: 'c2',
        name: 'Bicho Urbano',
        tax_id: null,
        phone: null,
        email: null,
        status: 'ACTIVE',
        address_zip_code: null,
        address_street: null,
        address_number: null,
        address_neighborhood: null,
        address_city: null,
        address_state: null,
        address_complement: null,
        notes: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        row_version: 1,
      }),
    ),
  )
  renderWithProviders(<ClinicsPage />)

  await user.click(await screen.findByRole('button', { name: /Nova clínica/i }))
  await user.type(screen.getByLabelText('Nome da clínica'), 'Bicho Urbano')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: 'Nova clínica' })).not.toBeInTheDocument(),
  )
  expect(await screen.findByRole('heading', { name: 'Bicho Urbano' })).toBeInTheDocument()
})
