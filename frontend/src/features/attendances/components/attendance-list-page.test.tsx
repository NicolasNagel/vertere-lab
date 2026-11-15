import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { AttendanceListPage } from './attendance-list-page'

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

function clinicsHandler() {
  return http.get('/api/v1/clinics', () =>
    HttpResponse.json({
      items: [{ id: 'c1', name: 'Clínica Central', status: 'ACTIVE' }],
      total: 1,
      page: 1,
      page_size: 100,
    }),
  )
}

function veterinariansHandler() {
  return http.get('/api/v1/veterinarians', () =>
    HttpResponse.json({
      items: [
        {
          id: 'v1',
          name: 'Dra. Ana',
          crmv: 'CRMV-SC 1234',
          phone: null,
          email: null,
          is_autonomous: true,
          status: 'ACTIVE',
          notes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          row_version: 1,
          clinics: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    }),
  )
}

function speciesHandler() {
  return http.get('/api/v1/species', () =>
    HttpResponse.json({
      items: [{ id: 's1', name: 'Canino', created_at: '2026-01-01T00:00:00Z' }],
    }),
  )
}

function patientsHandler() {
  return http.get('/api/v1/patients', () =>
    HttpResponse.json({
      items: [
        {
          id: 'p1',
          name: 'Bidu',
          species_id: 's1',
          sex: 'MALE',
          breed: null,
          age_description: '4 anos',
          owner_name: 'Maria Souza',
          owner_phone: null,
          owner_document: null,
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

function attendanceItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 'a1',
    clinic_id: 'c1',
    veterinarian_id: 'v1',
    patient_id: 'p1',
    service_date: '2026-01-05',
    notes: null,
    status: 'CONFIRMED',
    items: [
      {
        id: 'ai1',
        exam_id: 'e1',
        exam_code: 'HEMO',
        exam_name: 'Hemograma',
        price_base: '100.00',
        components: [],
        quantity: 1,
        discount_amount: '0.00',
        surcharge_amount: '0.00',
        total_amount: '100.00',
        override_reason: null,
        status: 'ACTIVE',
      },
    ],
    billing_competence: '2026-01-01',
    subtotal: '100.00',
    discount_total: '0.00',
    surcharge_total: '0.00',
    on_call_fee: '0.00',
    grand_total: '100.00',
    protocol_number: 'P000001/26',
    cancel_reason: null,
    created_at: '2026-01-05T10:00:00Z',
    updated_at: '2026-01-05T10:00:00Z',
    row_version: 2,
    ...overrides,
  }
}

function attendancesHandler(items: Record<string, unknown>[]) {
  return http.get('/api/v1/attendances', () =>
    HttpResponse.json({ items, total: items.length, page: 1, page_size: 20 }),
  )
}

function statusCountsHandler(byStatus: Record<string, number> = { CONFIRMED: 1, CANCELLED: 1 }) {
  return http.get('/api/v1/attendances/status-counts', () =>
    HttpResponse.json({
      total: Object.values(byStatus).reduce((sum, count) => sum + count, 0),
      by_status: byStatus,
      billed_total: '0.00',
    }),
  )
}

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('lists attendances with resolved names, shows drafts without protocol or total and gates by permission', async () => {
  const lookups = [clinicsHandler(), veterinariansHandler(), speciesHandler(), patientsHandler()]

  // Sem attendances.read.
  server.use(meHandler([]), ...lookups)
  let view = renderWithProviders(<AttendanceListPage />)
  expect(
    await screen.findByText('Você não tem permissão para visualizar atendimentos.'),
  ).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  // Confirmado: nomes resolvidos de clínica, veterinário e paciente.
  server.use(
    meHandler(['attendances.read', 'pricing.read']),
    ...lookups,
    statusCountsHandler(),
    attendancesHandler([
      attendanceItem({ service_date: '2026-07-05', created_at: '2026-08-01T10:00:00Z' }),
    ]),
  )
  view = renderWithProviders(<AttendanceListPage />)
  expect(await screen.findByText('P000001/26')).toBeInTheDocument()
  expect(screen.getByText('Data · Hora')).toBeInTheDocument()
  expect(screen.getByText(/05\/07 · \d{2}:00/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Competência/ })).toBeInTheDocument()
  expect(screen.queryByLabelText('Mês')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Ano')).not.toBeInTheDocument()
  // A tabela agora é um <table> real: a primeira linha é o cabeçalho.
  const dataRow = within(screen.getAllByRole('row')[1] as HTMLElement)
  expect(dataRow.getByText('Clínica Central')).toBeInTheDocument()
  expect(dataRow.getByText('Dra. Ana')).toBeInTheDocument()
  expect(dataRow.getByText('Bidu')).toBeInTheDocument()
  expect(dataRow.getByText(/4 anos/)).toBeInTheDocument()
  expect(dataRow.getByText('Hemograma')).toBeInTheDocument()
  expect(dataRow.getByText('R$ 100,00')).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: 'Valor' })).toBeInTheDocument()
  expect(screen.getByText('Valor atendido')).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  // Sem pricing.read: nem a coluna Valor nem o cartão de valor aparecem.
  server.use(
    meHandler(['attendances.read']),
    ...lookups,
    statusCountsHandler(),
    attendancesHandler([attendanceItem()]),
  )
  view = renderWithProviders(<AttendanceListPage />)
  expect(await screen.findByText('P000001/26')).toBeInTheDocument()
  expect(screen.queryByRole('columnheader', { name: 'Valor' })).not.toBeInTheDocument()
  expect(screen.queryByText('Valor atendido')).not.toBeInTheDocument()
  expect(screen.queryByText(/R\$/)).not.toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  // Rascunho: sem protocolo nem total.
  server.use(
    meHandler(['attendances.read', 'pricing.read']),
    ...lookups,
    statusCountsHandler(),
    attendancesHandler([
      attendanceItem({ status: 'DRAFT', items: [], protocol_number: null, grand_total: '0.00' }),
    ]),
  )
  renderWithProviders(<AttendanceListPage />)
  const draftRow = within((await screen.findAllByRole('row'))[1] as HTMLElement)
  expect(draftRow.getAllByText('Rascunho')).toHaveLength(2) // protocolo + status
  expect(draftRow.getByText('—', { selector: 'td' })).toBeInTheDocument() // sem total
})

test('re-filtering by status resets to page 1 and shows the empty state when nothing matches', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['attendances.read']),
    clinicsHandler(),
    veterinariansHandler(),
    speciesHandler(),
    patientsHandler(),
    statusCountsHandler(),
    http.get('/api/v1/attendances', ({ request }) => {
      const status = new URL(request.url).searchParams.get('status')
      const items = status === 'CANCELLED' ? [] : [attendanceItem()]
      return HttpResponse.json({ items, total: items.length, page: 1, page_size: 20 })
    }),
  )
  renderWithProviders(<AttendanceListPage />)

  expect(await screen.findByText('P000001/26')).toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: /Cancelado/ }))

  await waitFor(() =>
    expect(
      screen.getByText('Nenhum atendimento encontrado para os filtros selecionados.'),
    ).toBeInTheDocument(),
  )
})

test('debounces the protocol search and warns when a name lookup fails', async () => {
  const user = userEvent.setup()
  const searches: (string | null)[] = []
  server.use(
    meHandler(['attendances.read']),
    clinicsHandler(),
    veterinariansHandler(),
    speciesHandler(),
    statusCountsHandler(),
    http.get('/api/v1/patients', () => HttpResponse.json({}, { status: 500 })),
    http.get('/api/v1/attendances', ({ request }) => {
      searches.push(new URL(request.url).searchParams.get('protocol_number'))
      return HttpResponse.json({
        items: [attendanceItem()],
        total: 1,
        page: 1,
        page_size: 20,
      })
    }),
  )
  renderWithProviders(<AttendanceListPage />)

  // Falha ao carregar pacientes não some em silêncio: a lista segue e avisa.
  expect(await screen.findByText('P000001/26')).toBeInTheDocument()
  expect(
    await screen.findByText(
      /Não foi possível carregar nomes de clínicas, veterinários ou pacientes/,
    ),
  ).toBeInTheDocument()

  // Uma digitação rápida gera uma única busca com o texto final, não uma por tecla.
  await user.type(screen.getByPlaceholderText('Buscar protocolo...'), 'P0000')
  await waitFor(() => expect(searches.at(-1)).toBe('P0000'))
  expect(searches.filter((value) => value !== null)).toEqual(['P0000'])
})

function timelineHandler(attendanceId = 'a1') {
  return http.get(`/api/v1/attendances/${attendanceId}/timeline`, () =>
    HttpResponse.json({
      items: [
        {
          id: 't2',
          occurred_at: '2026-01-05T10:05:00Z',
          actor_user_id: 'u1',
          actor_name: 'Ana Souza',
          action: 'attendances.confirmed',
          before_state: null,
          after_state: null,
          reason: null,
        },
        {
          id: 't1',
          occurred_at: '2026-01-05T10:00:00Z',
          actor_user_id: 'u1',
          action: 'attendances.draft_created',
          before_state: null,
          after_state: null,
          reason: null,
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    }),
  )
}

function useListHandlers(permissions: string[], items: Record<string, unknown>[]) {
  server.use(
    meHandler(permissions),
    clinicsHandler(),
    veterinariansHandler(),
    speciesHandler(),
    patientsHandler(),
    statusCountsHandler(),
    attendancesHandler(items),
    timelineHandler(),
  )
}

test('clicking a row opens the summary popover with exams, totals and history, and Escape closes it', async () => {
  const user = userEvent.setup()
  useListHandlers(
    ['attendances.read', 'pricing.read'],
    [attendanceItem({ discount_total: '10.00', grand_total: '90.00', subtotal: '100.00' })],
  )
  renderWithProviders(<AttendanceListPage />)

  const row = (await screen.findAllByRole('row'))[1] as HTMLElement
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await user.click(row)

  const popover = await screen.findByRole('dialog', { name: 'P000001/26' })
  const summary = within(popover)
  expect(summary.getByText('Dra. Ana')).toBeInTheDocument()
  expect(summary.getByText('Clínica Central')).toBeInTheDocument()
  expect(summary.getByText(/Bidu/)).toBeInTheDocument()
  expect(summary.getByText('Tutor: Maria Souza')).toBeInTheDocument()
  expect(summary.getByText('Hemograma')).toBeInTheDocument()
  expect(within(summary.getByLabelText('Valores')).getByText('R$ 90,00')).toBeInTheDocument()
  expect(await summary.findByText('Atendimento confirmado')).toBeInTheDocument()
  expect(summary.getByText(/Ana Souza/)).toBeInTheDocument()
  expect(summary.getByText('Rascunho criado')).toBeInTheDocument()
  expect(summary.getByRole('link', { name: 'Abrir atendimento' })).toHaveAttribute(
    'href',
    '/operacao/a1',
  )

  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(row).toHaveFocus()
})

test('the summary popover hides every amount from users without pricing.read', async () => {
  const user = userEvent.setup()
  useListHandlers(['attendances.read'], [attendanceItem({ discount_total: '10.00' })])
  renderWithProviders(<AttendanceListPage />)

  await user.click((await screen.findAllByRole('row'))[1] as HTMLElement)
  const summary = within(await screen.findByRole('dialog', { name: 'P000001/26' }))

  expect(summary.getByText('Hemograma')).toBeInTheDocument()
  expect(summary.queryByLabelText('Valores')).not.toBeInTheDocument()
  expect(summary.queryByText(/R\$/)).not.toBeInTheDocument()
})

test('cancel button in the popover needs attendances.cancel and a cancellable status', async () => {
  const user = userEvent.setup()

  // Sem permissão de cancelar.
  useListHandlers(['attendances.read'], [attendanceItem()])
  let view = renderWithProviders(<AttendanceListPage />)
  await user.click((await screen.findAllByRole('row'))[1] as HTMLElement)
  const noPermission = within(await screen.findByRole('dialog', { name: 'P000001/26' }))
  expect(noPermission.queryByRole('button', { name: 'Mais ações' })).not.toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  // Já cancelado.
  useListHandlers(
    ['attendances.read', 'attendances.cancel'],
    [attendanceItem({ status: 'CANCELLED', cancel_reason: 'Duplicado' })],
  )
  view = renderWithProviders(<AttendanceListPage />)
  await user.click((await screen.findAllByRole('row'))[1] as HTMLElement)
  const cancelled = within(await screen.findByRole('dialog', { name: 'P000001/26' }))
  expect(cancelled.queryByRole('button', { name: 'Mais ações' })).not.toBeInTheDocument()
  expect(cancelled.getByText('Motivo do cancelamento: Duplicado')).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  // Confirmado com permissão: o botão fecha o popover e abre o modal de motivo.
  useListHandlers(['attendances.read', 'attendances.cancel'], [attendanceItem()])
  renderWithProviders(<AttendanceListPage />)
  await user.click((await screen.findAllByRole('row'))[1] as HTMLElement)
  const popover = within(await screen.findByRole('dialog', { name: 'P000001/26' }))
  await user.click(popover.getByRole('button', { name: 'Mais ações' }))
  await user.click(popover.getByRole('menuitem', { name: 'Cancelar atendimento' }))

  expect(await screen.findByRole('button', { name: 'Confirmar cancelamento' })).toBeInTheDocument()
  expect(screen.queryByRole('dialog', { name: 'P000001/26' })).not.toBeInTheDocument()
})

test('clicking the details link inside a row does not open the popover, and reopening on another row shows that attendance', async () => {
  const user = userEvent.setup()
  useListHandlers(
    ['attendances.read'],
    [attendanceItem(), attendanceItem({ id: 'a2', protocol_number: 'P000002/26' })],
  )
  server.use(timelineHandler('a2'))
  renderWithProviders(<AttendanceListPage />)

  const rows = await screen.findAllByRole('row')
  await user.click(within(rows[1] as HTMLElement).getByRole('link'))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

  await user.click(rows[1] as HTMLElement)
  expect(await screen.findByRole('dialog', { name: 'P000001/26' })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  await user.click(rows[2] as HTMLElement)
  expect(await screen.findByRole('dialog', { name: 'P000002/26' })).toBeInTheDocument()
  expect(screen.getAllByRole('dialog')).toHaveLength(1)
})
