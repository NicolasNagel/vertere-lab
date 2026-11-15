import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { VeterinarianDetailPage } from './veterinarian-detail-page'
import { VeterinarianFormPage } from './veterinarian-form-page'
import { VeterinariansPage } from './veterinarians-page'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

const READ = ['veterinarians.read']
const MANAGE = ['veterinarians.read', 'veterinarians.manage']

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

function apiVeterinarian(overrides: Record<string, unknown> = {}) {
  return {
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
    ...overrides,
  }
}

function listHandler(items = [apiVeterinarian()]) {
  return http.get('/api/v1/veterinarians', () =>
    HttpResponse.json({ items, total: items.length, page: 1, page_size: 25 }),
  )
}

function detailHandler(overrides: Record<string, unknown> = {}, clinics: unknown[] = []) {
  const body = { ...apiVeterinarian(overrides), clinics }
  return http.get(`/api/v1/veterinarians/${body.id}`, () => HttpResponse.json(body))
}

function clinicsHandler(items: unknown[] = []) {
  return http.get('/api/v1/clinics', () =>
    HttpResponse.json({ items, total: items.length, page: 1, page_size: 100 }),
  )
}

function apiClinic(id: string, name: string) {
  return {
    id,
    name,
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
  }
}

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/cadastros/veterinarios" element={<VeterinariansPage />} />
            <Route path="/cadastros/veterinarios/novo" element={<VeterinarianFormPage />} />
            <Route
              path="/cadastros/veterinarios/:veterinarianId"
              element={<VeterinarianDetailPage />}
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('lists veterinarians and offers "Novo veterinário" only with veterinarians.manage', async () => {
  server.use(meHandler(READ), listHandler())
  const view = renderAt('/cadastros/veterinarios')

  expect(await screen.findByText('Dra. Fabianna Garcia')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Novo veterinário/i })).not.toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  server.use(meHandler(MANAGE), listHandler())
  renderAt('/cadastros/veterinarios')
  expect(await screen.findByRole('link', { name: /Novo veterinário/i })).toBeInTheDocument()
})

test('filters by link type with the icon dropdown and sends is_autonomous to the server', async () => {
  const user = userEvent.setup()
  const seen: (string | null)[] = []
  server.use(
    meHandler(READ),
    http.get('/api/v1/veterinarians', ({ request }) => {
      const isAutonomous = new URL(request.url).searchParams.get('is_autonomous')
      seen.push(isAutonomous)
      const items =
        isAutonomous === 'true'
          ? [
              apiVeterinarian({
                id: 'v3',
                name: 'Karin Witt',
                is_autonomous: true,
              }),
            ]
          : [apiVeterinarian()]
      return HttpResponse.json({
        items,
        total: items.length,
        page: 1,
        page_size: 25,
      })
    }),
  )
  renderAt('/cadastros/veterinarios')

  expect(await screen.findByText('Dra. Fabianna Garcia')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Vínculo/ }))
  await user.click(await screen.findByRole('option', { name: 'Autônomos' }))
  expect(await screen.findByText('Karin Witt')).toBeInTheDocument()
  expect(screen.queryByText('Dra. Fabianna Garcia')).not.toBeInTheDocument()
  expect(seen).toContain('true')
})

test('shows an inactive autonomous veterinarian with both marks in the row', async () => {
  server.use(
    meHandler(READ),
    listHandler([
      apiVeterinarian({
        id: 'v9',
        name: 'Aline Cabral Silva',
        is_autonomous: true,
        status: 'INACTIVE',
      }),
    ]),
  )
  renderAt('/cadastros/veterinarios')
  const row = (await screen.findByText('Aline Cabral Silva')).closest('tr') as HTMLElement
  expect(within(row).getByText('Autônomo')).toBeInTheDocument()
  expect(within(row).getByText('Inativo')).toBeInTheDocument()
})

test('row click opens the summary popover with the linked clinics and a link to the detail', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(READ),
    listHandler(),
    detailHandler({}, [{ clinic_id: 'c1', clinic_name: 'Schweitzer', primary_clinic: true }]),
  )
  renderAt('/cadastros/veterinarios')

  await user.click(await screen.findByRole('button', { name: 'Dra. Fabianna Garcia' }))
  const summary = within(await screen.findByRole('dialog'))
  expect(await summary.findByText(/Schweitzer/)).toBeInTheDocument()
  expect(summary.getByRole('link', { name: 'Abrir veterinário' })).toHaveAttribute(
    'href',
    '/cadastros/veterinarios/v1',
  )
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

test('creates veterinarians: autonomous, blocked without clinic, and with a linked clinic', async () => {
  const user = userEvent.setup()

  const autonomousSpy = vi.fn()
  server.use(
    meHandler(MANAGE),
    listHandler(),
    clinicsHandler(),
    http.post('/api/v1/veterinarians', async ({ request }) => {
      autonomousSpy(await request.json())
      return HttpResponse.json(apiVeterinarian({ id: 'v2', is_autonomous: true }), { status: 201 })
    }),
  )
  let view = renderAt('/cadastros/veterinarios/novo')
  await user.type(await screen.findByLabelText('Nome'), 'Dr. Michael Neves')
  await user.type(screen.getByLabelText('CRMV'), 'CRMV-SC 08230')
  await user.click(screen.getByLabelText('Veterinário autônomo'))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(autonomousSpy).toHaveBeenCalled())
  expect(await screen.findByRole('heading', { name: 'Veterinários' })).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  const blockedSpy = vi.fn()
  server.use(
    meHandler(MANAGE),
    clinicsHandler(),
    http.post('/api/v1/veterinarians', () => {
      blockedSpy()
      return HttpResponse.json({}, { status: 201 })
    }),
  )
  view = renderAt('/cadastros/veterinarios/novo')
  await user.type(await screen.findByLabelText('Nome'), 'Vet Sem Clínica')
  await user.type(screen.getByLabelText('CRMV'), 'CRMV-SC 00001')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  expect(
    await screen.findByText('Selecione ao menos uma clínica ou marque como autônomo.'),
  ).toBeInTheDocument()
  expect(blockedSpy).not.toHaveBeenCalled()
  view.unmount()
  server.resetHandlers()

  const createSpy = vi.fn()
  server.use(
    meHandler(MANAGE),
    listHandler(),
    clinicsHandler([apiClinic('c1', 'Schweitzer')]),
    http.post('/api/v1/veterinarians', async ({ request }) => {
      createSpy(await request.json())
      return HttpResponse.json(apiVeterinarian({ id: 'v2' }), { status: 201 })
    }),
  )
  renderAt('/cadastros/veterinarios/novo')
  await user.type(await screen.findByLabelText('Nome'), 'Dr. Michael Neves')
  await user.type(screen.getByLabelText('CRMV'), 'CRMV-SC 08230')
  await user.click(await screen.findByLabelText('Schweitzer'))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() =>
    expect(createSpy).toHaveBeenCalledWith(
      expect.objectContaining({ clinic_ids: ['c1'], primary_clinic_id: 'c1' }),
    ),
  )
})

test('detail block edit needs a reason and sends it with the whole veterinarian', async () => {
  const user = userEvent.setup()
  const patchSpy = vi.fn()
  server.use(
    meHandler(MANAGE),
    detailHandler({ phone: '48999990000' }),
    http.patch('/api/v1/veterinarians/v1', async ({ request }) => {
      patchSpy(await request.json())
      return HttpResponse.json(apiVeterinarian({ name: 'Dra. Fabi', row_version: 2 }))
    }),
  )
  renderAt('/cadastros/veterinarios/v1')

  await user.click(await screen.findByRole('button', { name: 'Editar identificação' }))
  const name = screen.getByLabelText('Nome')
  await user.clear(name)
  await user.type(name, 'Dra. Fabi')
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Nome social')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(patchSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Dra. Fabi',
        crmv: 'CRMV-SC 04567',
        phone: '48999990000',
        reason: 'Nome social',
        expected_row_version: 1,
      }),
    ),
  )
})

test('detail offers to reload on a version conflict and hides Editar without permission', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(MANAGE),
    detailHandler(),
    http.patch('/api/v1/veterinarians/v1', () =>
      HttpResponse.json(
        {
          error: {
            code: 'CONFLICT',
            message: 'Foi alterado por outra pessoa.',
            details: [],
          },
        },
        { status: 409 },
      ),
    ),
  )
  const view = renderAt('/cadastros/veterinarios/v1')
  await user.click(await screen.findByRole('button', { name: 'Editar contato' }))
  await user.type(screen.getByLabelText('Telefone'), '48911112222')
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Telefone novo')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  expect(await screen.findByRole('button', { name: 'Recarregar veterinário' })).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  server.use(meHandler(READ), detailHandler())
  renderAt('/cadastros/veterinarios/v1')
  expect(await screen.findByRole('heading', { name: 'Dra. Fabianna Garcia' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Editar/ })).not.toBeInTheDocument()
})

function pagedClinicsHandler(all: ReturnType<typeof apiClinic>[]) {
  return http.get('/api/v1/clinics', ({ request }) => {
    const url = new URL(request.url)
    const search = (url.searchParams.get('search') ?? '').toLowerCase()
    const page = Number(url.searchParams.get('page') ?? 1)
    const pageSize = Number(url.searchParams.get('page_size') ?? 20)
    const filtered = all.filter((clinic) => clinic.name.toLowerCase().includes(search))
    return HttpResponse.json({
      items: filtered.slice((page - 1) * pageSize, page * pageSize),
      total: filtered.length,
      page,
      page_size: pageSize,
    })
  })
}

const MANY_CLINICS = Array.from({ length: 150 }, (_, index) =>
  apiClinic(`c${index + 1}`, `Clínica ${String(index + 1).padStart(3, '0')}`),
)

test('links 100+ clinics in one batch with a single reason', async () => {
  const user = userEvent.setup()
  const patchSpy = vi.fn()
  server.use(
    meHandler(MANAGE),
    pagedClinicsHandler(MANY_CLINICS),
    detailHandler({}, [{ clinic_id: 'c1', clinic_name: 'Clínica 001', primary_clinic: true }]),
    http.patch('/api/v1/veterinarians/v1/clinics', async ({ request }) => {
      patchSpy(await request.json())
      return new HttpResponse(null, { status: 204 })
    }),
  )
  renderAt('/cadastros/veterinarios/v1')

  await user.click(await screen.findByRole('button', { name: 'Editar clínicas vinculadas' }))
  expect(screen.getByText('1 clínica selecionada')).toBeInTheDocument()
  // a lista é paginada: só 10 por vez, mesmo com 150 clínicas
  expect(await screen.findByLabelText('Clínica 010')).toBeInTheDocument()
  expect(screen.queryByLabelText('Clínica 011')).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Selecionar todas (150)' }))
  expect(await screen.findByText('150 clínicas selecionadas')).toBeInTheDocument()
  expect(screen.getByText('Vincular 149 · Desvincular 0')).toBeInTheDocument()

  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Carteira nova')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(patchSpy).toHaveBeenCalledTimes(1))
  const body = patchSpy.mock.calls[0]?.[0] as Record<string, unknown>
  expect((body.add_clinic_ids as string[]).length).toBe(149)
  expect(body.remove_clinic_ids).toEqual([])
  expect(body.primary_clinic_id).toBe('c1')
  expect(body.expected_row_version).toBe(1)
  expect(body.reason).toBe('Carteira nova')
})

test('search narrows the list on the server and select-all applies only to the filtered ones', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(MANAGE),
    pagedClinicsHandler(MANY_CLINICS),
    detailHandler({ is_autonomous: true }, []),
  )
  renderAt('/cadastros/veterinarios/v1')

  await user.click(await screen.findByRole('button', { name: 'Editar clínicas vinculadas' }))
  await user.type(screen.getByLabelText('Buscar clínica'), 'Clínica 1')
  const select = await screen.findByRole('button', { name: 'Selecionar as 51 filtradas' })
  await user.click(select)
  expect(await screen.findByText('51 clínicas selecionadas')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Limpar seleção' }))
  expect(await screen.findByText('0 clínicas selecionadas')).toBeInTheDocument()
})

test('a non-autonomous veterinarian cannot save without a clinic; an autonomous one can', async () => {
  const user = userEvent.setup()
  const patchSpy = vi.fn()
  const linked = [{ clinic_id: 'c1', clinic_name: 'Schweitzer', primary_clinic: true }]
  server.use(
    meHandler(MANAGE),
    clinicsHandler(),
    detailHandler({}, linked),
    http.patch('/api/v1/veterinarians/v1/clinics', async ({ request }) => {
      patchSpy(await request.json())
      return new HttpResponse(null, { status: 204 })
    }),
  )
  const view = renderAt('/cadastros/veterinarios/v1')
  await user.click(await screen.findByRole('button', { name: 'Editar clínicas vinculadas' }))
  await user.click(screen.getByRole('button', { name: 'Remover Schweitzer' }))
  expect(
    screen.getByText('Veterinário não autônomo precisa de ao menos uma clínica vinculada.'),
  ).toBeInTheDocument()
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Saiu')
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  view.unmount()
  server.resetHandlers()

  server.use(
    meHandler(MANAGE),
    clinicsHandler(),
    detailHandler({ is_autonomous: true }, linked),
    http.patch('/api/v1/veterinarians/v1/clinics', async ({ request }) => {
      patchSpy(await request.json())
      return new HttpResponse(null, { status: 204 })
    }),
  )
  renderAt('/cadastros/veterinarios/v1')
  await user.click(await screen.findByRole('button', { name: 'Editar clínicas vinculadas' }))
  await user.click(screen.getByRole('button', { name: 'Remover Schweitzer' }))
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Virou autônomo')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() =>
    expect(patchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ remove_clinic_ids: ['c1'], add_clinic_ids: [] }),
    ),
  )
})
