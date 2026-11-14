import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
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

function apiVeterinarian(overrides: Record<string, unknown> = {}) {
  return {
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
    ...overrides,
  }
}

function emptyClinicsHandler() {
  return http.get('/api/v1/clinics', () =>
    HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
  )
}

test('lists veterinarians and offers "Novo vet" only with veterinarians.manage', async () => {
  server.use(meHandler(['veterinarians.read']), veterinariansListHandler())
  const view = renderWithProviders(<VeterinariansPage />)

  expect(await screen.findByText('Dra. Fabianna Garcia')).toBeInTheDocument()
  expect(screen.getByText('1 ativo')).toBeInTheDocument() // singular com um único ativo
  expect(screen.queryByRole('button', { name: /Novo vet/i })).not.toBeInTheDocument()
  restart(view)

  server.use(meHandler(['veterinarians.read', 'veterinarians.manage']), veterinariansListHandler())
  renderWithProviders(<VeterinariansPage />)
  expect(await screen.findByRole('button', { name: /Novo vet/i })).toBeInTheDocument()
})

test('filters by autonomous type and shows the inactive badge even for an autonomous veterinarian', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['veterinarians.read']),
    http.get('/api/v1/veterinarians', ({ request }) => {
      const isAutonomous = new URL(request.url).searchParams.get('is_autonomous')
      const items =
        isAutonomous === 'true'
          ? [
              apiVeterinarian({
                id: 'v3',
                name: 'Karin Witt',
                crmv: 'CRMV-SC 04127',
              }),
            ]
          : [
              apiVeterinarian({
                id: 'v1',
                name: 'Dra. Fabianna Garcia',
                crmv: 'CRMV-SC 04567',
                is_autonomous: false,
              }),
            ]
      return HttpResponse.json({ items, total: 1, page: 1, page_size: 100 })
    }),
  )
  const view = renderWithProviders(<VeterinariansPage />)

  expect(await screen.findByText('Dra. Fabianna Garcia')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Autônomos' }))
  expect(await screen.findByText('Karin Witt')).toBeInTheDocument()
  expect(screen.queryByText('Dra. Fabianna Garcia')).not.toBeInTheDocument()
  restart(view)

  // Regressão: o selo da linha era if/else (Autônomo *ou* status), então um autônomo
  // inativo aparecia igual a um ativo na lista (achado em QA manual com dado importado).
  server.use(
    meHandler(['veterinarians.read']),
    http.get('/api/v1/veterinarians', () =>
      HttpResponse.json({
        items: [
          apiVeterinarian({
            id: 'v9',
            name: 'Aline Cabral Silva',
            crmv: '13552',
            status: 'INACTIVE',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 100,
      }),
    ),
  )
  renderWithProviders(<VeterinariansPage />)
  const row = (await screen.findByText('Aline Cabral Silva')).closest('button') as HTMLElement
  expect(within(row).getByText('Autônomo')).toBeInTheDocument()
  expect(within(row).getByText('Inativo')).toBeInTheDocument()
})

test('creates veterinarians: autonomous, blocked without clinic, and with a linked clinic', async () => {
  const user = userEvent.setup()
  const common = [
    meHandler(['veterinarians.read', 'veterinarians.manage']),
    veterinariansListHandler(),
  ]

  // Autônomo: cria e volta ao detalhe.
  server.use(
    ...common,
    emptyClinicsHandler(),
    http.post('/api/v1/veterinarians', () => HttpResponse.json(apiVeterinarian(), { status: 201 })),
    http.get('/api/v1/veterinarians/v2', () =>
      HttpResponse.json({ ...apiVeterinarian(), clinics: [] }),
    ),
  )
  let view = renderWithProviders(<VeterinariansPage />)
  await user.click(await screen.findByRole('button', { name: /Novo vet/i }))
  await user.type(screen.getByLabelText('Nome'), 'Dr. Michael Neves')
  await user.type(screen.getByLabelText('CRMV'), 'CRMV-SC 08230')
  await user.click(screen.getByLabelText('Veterinário autônomo'))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: 'Novo vet' })).not.toBeInTheDocument(),
  )
  expect(await screen.findByRole('heading', { name: 'Dr. Michael Neves' })).toBeInTheDocument()
  restart(view)

  // Não autônomo sem clínica é bloqueado no cliente e nada é enviado.
  const blockedSpy = vi.fn()
  server.use(
    ...common,
    emptyClinicsHandler(),
    http.post('/api/v1/veterinarians', () => {
      blockedSpy()
      return HttpResponse.json({}, { status: 201 })
    }),
  )
  view = renderWithProviders(<VeterinariansPage />)
  await user.click(await screen.findByRole('button', { name: /Novo vet/i }))
  await user.type(screen.getByLabelText('Nome'), 'Vet Sem Clínica')
  await user.type(screen.getByLabelText('CRMV'), 'CRMV-SC 00001')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  expect(
    await screen.findByText('Selecione ao menos uma clínica ou marque como autônomo.'),
  ).toBeInTheDocument()
  expect(blockedSpy).not.toHaveBeenCalled()
  restart(view)

  // Não autônomo com clínica: envia a clínica na mesma requisição.
  const createSpy = vi.fn()
  server.use(
    ...common,
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
      return HttpResponse.json(apiVeterinarian({ is_autonomous: false }), {
        status: 201,
      })
    }),
    http.get('/api/v1/veterinarians/v2', () =>
      HttpResponse.json({
        ...apiVeterinarian({ is_autonomous: false }),
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
    emptyClinicsHandler(),
    http.get('/api/v1/veterinarians/v1', () =>
      HttpResponse.json({
        ...apiVeterinarian({
          id: 'v1',
          name: 'Dra. Fabianna Garcia',
          crmv: 'CRMV-SC 04567',
        }),
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
