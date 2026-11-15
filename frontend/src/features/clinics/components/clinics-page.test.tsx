import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { ClinicFormPage } from './clinic-form-page'
import { ClinicsPage } from './clinics-page'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function meHandler(permissions: string[]) {
  return http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      user: {
        id: 'u1',
        email: 'a@b.com',
        full_name: 'A',
        role_id: 'r1',
        role_name: 'LAB_ADMIN',
      },
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

function renderWithProviders(children: ReactNode, initialPath = '/cadastros/clinicas') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialPath]}>{children}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

function apiClinic(overrides: Record<string, unknown> = {}) {
  return {
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
    ...overrides,
  }
}

test('lists clinics in a table with the masked CNPJ and singular count, without "Nova clínica" for read-only users', async () => {
  server.use(meHandler(['clinics.read']), clinicsListHandler())
  renderWithProviders(
    <Routes>
      <Route path="/cadastros/clinicas" element={<ClinicsPage />} />
    </Routes>,
  )

  expect(await screen.findByRole('button', { name: 'Schweitzer' })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: 'CNPJ' })).toBeInTheDocument()
  expect(screen.getByText('78.977.352/0001-99')).toBeInTheDocument()
  expect(screen.queryByText('78977352000199')).not.toBeInTheDocument()
  expect(screen.getByText('Mostrando 1–1 de 1 clínica')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Nova clínica/i })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Ações para / })).not.toBeInTheDocument()
})

test('selecting a row opens the detail panel with an edit link only for managers', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['clinics.read', 'clinics.manage']),
    clinicsListHandler(),
    http.get('/api/v1/clinics/c1', () =>
      HttpResponse.json(apiClinic({ id: 'c1', name: 'Schweitzer', tax_id: '78977352000199' })),
    ),
  )
  renderWithProviders(
    <Routes>
      <Route path="/cadastros/clinicas" element={<ClinicsPage />} />
    </Routes>,
  )

  await user.click(await screen.findByRole('button', { name: 'Schweitzer' }))
  expect(await screen.findByRole('heading', { name: 'Schweitzer' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Editar' })).toHaveAttribute(
    'href',
    '/cadastros/clinicas/c1/editar',
  )
  expect(screen.getByRole('button', { name: 'Ações para Schweitzer' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Nova clínica/i })).toHaveAttribute(
    'href',
    '/cadastros/clinicas/nova',
  )
})

test('the form screen creates a clinic and returns to the list without opening the detail', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['clinics.read', 'clinics.manage']),
    clinicsListHandler(),
    http.post('/api/v1/clinics', () => HttpResponse.json(apiClinic(), { status: 201 })),
    http.get('/api/v1/clinics/c2', () => HttpResponse.json(apiClinic())),
  )
  renderWithProviders(
    <Routes>
      <Route path="/cadastros/clinicas/nova" element={<ClinicFormPage />} />
      <Route path="/cadastros/clinicas" element={<ClinicsPage />} />
    </Routes>,
    '/cadastros/clinicas/nova',
  )

  await user.type(await screen.findByLabelText('Nome da clínica'), 'Bicho Urbano')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByRole('heading', { name: 'Clínicas parceiras' })).toBeInTheDocument()
  // Voltar da tela de formulário não abre o detalhe: ele só abre ao clicar numa linha.
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('a double click on Salvar sends a single create request', async () => {
  const user = userEvent.setup()
  let posts = 0
  server.use(
    meHandler(['clinics.read', 'clinics.manage']),
    clinicsListHandler(),
    http.post('/api/v1/clinics', () => {
      posts += 1
      return HttpResponse.json(apiClinic(), { status: 201 })
    }),
    http.get('/api/v1/clinics/c2', () => HttpResponse.json(apiClinic())),
  )
  renderWithProviders(
    <Routes>
      <Route path="/cadastros/clinicas/nova" element={<ClinicFormPage />} />
      <Route path="/cadastros/clinicas" element={<ClinicsPage />} />
    </Routes>,
    '/cadastros/clinicas/nova',
  )

  await user.type(await screen.findByLabelText('Nome da clínica'), 'Bicho Urbano')
  await user.dblClick(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByRole('heading', { name: 'Clínicas parceiras' })).toBeInTheDocument()
  expect(posts).toBe(1)
})
