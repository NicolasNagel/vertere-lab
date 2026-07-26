import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { VeterinariansPage } from './veterinarians-page'

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

function veterinariansListHandler() {
  return http.get('/api/v1/veterinarians', () =>
    HttpResponse.json({
      items: [
        {
          id: 'v1',
          name: 'Dra. Fabianna Garcia',
          crmv: 'CRMV-SC 04567',
          phone: null,
          email: null,
          is_autonomous: false,
          status: 'ACTIVE',
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

test('lists veterinarians returned by the API', async () => {
  server.use(meHandler(['veterinarians.read']), veterinariansListHandler())
  renderWithProviders(<VeterinariansPage />)

  expect(await screen.findByText('Dra. Fabianna Garcia')).toBeInTheDocument()
})

test('uses the singular form when there is exactly one active veterinarian', async () => {
  server.use(meHandler(['veterinarians.read']), veterinariansListHandler())
  renderWithProviders(<VeterinariansPage />)

  await screen.findByText('Dra. Fabianna Garcia')
  expect(screen.getByText('1 ativo')).toBeInTheDocument()
})

test('hides the "Novo vet" action for a user without veterinarians.manage', async () => {
  server.use(meHandler(['veterinarians.read']), veterinariansListHandler())
  renderWithProviders(<VeterinariansPage />)

  await screen.findByText('Dra. Fabianna Garcia')
  expect(screen.queryByRole('button', { name: /Novo vet/i })).not.toBeInTheDocument()
})

test('shows the "Novo vet" action for a user with veterinarians.manage', async () => {
  server.use(meHandler(['veterinarians.read', 'veterinarians.manage']), veterinariansListHandler())
  renderWithProviders(<VeterinariansPage />)

  expect(await screen.findByRole('button', { name: /Novo vet/i })).toBeInTheDocument()
})

test('creates a veterinarian and returns to the detail view', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['veterinarians.read', 'veterinarians.manage']),
    veterinariansListHandler(),
    http.get('/api/v1/clinics', () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
    ),
    http.post('/api/v1/veterinarians', () =>
      HttpResponse.json(
        {
          id: 'v2',
          name: 'Dr. Michael Neves',
          crmv: 'CRMV-SC 08230',
          phone: null,
          email: null,
          is_autonomous: true,
          status: 'ACTIVE',
          notes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
        },
        { status: 201 },
      ),
    ),
    http.get('/api/v1/veterinarians/v2', () =>
      HttpResponse.json({
        id: 'v2',
        name: 'Dr. Michael Neves',
        crmv: 'CRMV-SC 08230',
        phone: null,
        email: null,
        is_autonomous: true,
        status: 'ACTIVE',
        notes: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        row_version: 1,
        clinics: [],
      }),
    ),
  )
  renderWithProviders(<VeterinariansPage />)

  await user.click(await screen.findByRole('button', { name: /Novo vet/i }))
  await user.type(screen.getByLabelText('Nome'), 'Dr. Michael Neves')
  await user.type(screen.getByLabelText('CRMV'), 'CRMV-SC 08230')
  await user.click(screen.getByLabelText('Veterinário autônomo'))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: 'Novo vet' })).not.toBeInTheDocument(),
  )
  expect(await screen.findByRole('heading', { name: 'Dr. Michael Neves' })).toBeInTheDocument()
})

test('filters by autonomous type', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['veterinarians.read']),
    http.get('/api/v1/veterinarians', ({ request }) => {
      const url = new URL(request.url)
      const isAutonomous = url.searchParams.get('is_autonomous')
      if (isAutonomous === 'true') {
        return HttpResponse.json({
          items: [
            {
              id: 'v3',
              name: 'Karin Witt',
              crmv: 'CRMV-SC 04127',
              phone: null,
              email: null,
              is_autonomous: true,
              status: 'ACTIVE',
              notes: null,
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              row_version: 1,
            },
          ],
          total: 1,
          page: 1,
          page_size: 100,
        })
      }
      return HttpResponse.json({
        items: [
          {
            id: 'v1',
            name: 'Dra. Fabianna Garcia',
            crmv: 'CRMV-SC 04567',
            phone: null,
            email: null,
            is_autonomous: false,
            status: 'ACTIVE',
            notes: null,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
            row_version: 1,
          },
        ],
        total: 1,
        page: 1,
        page_size: 100,
      })
    }),
  )
  renderWithProviders(<VeterinariansPage />)

  expect(await screen.findByText('Dra. Fabianna Garcia')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Autônomos' }))

  expect(await screen.findByText('Karin Witt')).toBeInTheDocument()
  expect(screen.queryByText('Dra. Fabianna Garcia')).not.toBeInTheDocument()
})

test('blocks create for a non-autonomous veterinarian without a linked clinic', async () => {
  const user = userEvent.setup()
  const createSpy = vi.fn()
  server.use(
    meHandler(['veterinarians.read', 'veterinarians.manage']),
    veterinariansListHandler(),
    http.get('/api/v1/clinics', () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
    ),
    http.post('/api/v1/veterinarians', () => {
      createSpy()
      return HttpResponse.json({}, { status: 201 })
    }),
  )
  renderWithProviders(<VeterinariansPage />)

  await user.click(await screen.findByRole('button', { name: /Novo vet/i }))
  await user.type(screen.getByLabelText('Nome'), 'Vet Sem Clínica')
  await user.type(screen.getByLabelText('CRMV'), 'CRMV-SC 00001')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(
    await screen.findByText('Selecione ao menos uma clínica ou marque como autônomo.'),
  ).toBeInTheDocument()
  expect(createSpy).not.toHaveBeenCalled()
})

test('creates a veterinarian sending the selected clinic in the same request', async () => {
  const user = userEvent.setup()
  const createSpy = vi.fn()
  server.use(
    meHandler(['veterinarians.read', 'veterinarians.manage']),
    veterinariansListHandler(),
    http.get('/api/v1/clinics', () =>
      HttpResponse.json({
        items: [
          {
            id: 'c1',
            name: 'Schweitzer',
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
        ],
        total: 1,
        page: 1,
        page_size: 100,
      }),
    ),
    http.post('/api/v1/veterinarians', async ({ request }) => {
      createSpy(await request.json())
      return HttpResponse.json(
        {
          id: 'v2',
          name: 'Dr. Michael Neves',
          crmv: 'CRMV-SC 08230',
          phone: null,
          email: null,
          is_autonomous: false,
          status: 'ACTIVE',
          notes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
        },
        { status: 201 },
      )
    }),
    http.get('/api/v1/veterinarians/v2', () =>
      HttpResponse.json({
        id: 'v2',
        name: 'Dr. Michael Neves',
        crmv: 'CRMV-SC 08230',
        phone: null,
        email: null,
        is_autonomous: false,
        status: 'ACTIVE',
        notes: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        row_version: 1,
        clinics: [{ clinic_id: 'c1', clinic_name: 'Schweitzer', primary_clinic: true }],
      }),
    ),
  )
  renderWithProviders(<VeterinariansPage />)

  await user.click(await screen.findByRole('button', { name: /Novo vet/i }))
  await user.type(screen.getByLabelText('Nome'), 'Dr. Michael Neves')
  await user.type(screen.getByLabelText('CRMV'), 'CRMV-SC 08230')
  await user.click(await screen.findByLabelText('Schweitzer'))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(createSpy).toHaveBeenCalledWith(
      expect.objectContaining({ clinic_ids: ['c1'], primary_clinic_id: 'c1' }),
    ),
  )
  expect(await screen.findByText('Schweitzer')).toBeInTheDocument()
})

test('unlinks a clinic from the veterinarian detail card', async () => {
  const user = userEvent.setup()
  const unlinkSpy = vi.fn()
  server.use(
    meHandler(['veterinarians.read', 'veterinarians.manage']),
    veterinariansListHandler(),
    http.get('/api/v1/clinics', () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
    ),
    http.get('/api/v1/veterinarians/v1', () =>
      HttpResponse.json({
        id: 'v1',
        name: 'Dra. Fabianna Garcia',
        crmv: 'CRMV-SC 04567',
        phone: null,
        email: null,
        is_autonomous: true,
        status: 'ACTIVE',
        notes: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        row_version: 1,
        clinics: [{ clinic_id: 'c1', clinic_name: 'Schweitzer', primary_clinic: false }],
      }),
    ),
    http.delete('/api/v1/veterinarians/v1/clinics/c1', () => {
      unlinkSpy()
      return new HttpResponse(null, { status: 204 })
    }),
  )
  renderWithProviders(<VeterinariansPage />)

  await user.click(await screen.findByText('Dra. Fabianna Garcia'))
  await user.click(await screen.findByRole('button', { name: 'remover' }))

  await waitFor(() => expect(unlinkSpy).toHaveBeenCalled())
})
