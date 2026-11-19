import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { apiPatient, clinicsHandler, meHandler, speciesHandler } from '../../../test/patients-handlers'
import { PatientsPage } from './patients-page'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

const READ = ['patients.read']
const MANAGE = ['patients.read', 'patients.manage']

function pageOf(items: unknown[]) {
  return { items, total: items.length, page: 1, page_size: 25 }
}

/** Handlers comuns da lista: espécies, clínicas e o resumo. */
function baseHandlers(permissions: string[], summary = { total: 3, active: 2, inactive: 1 }) {
  return [
    meHandler(permissions),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/summary', () => HttpResponse.json(summary)),
  ]
}

function renderList(path = '/pacientes') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/pacientes" element={<PatientsPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('lists patients with species and clinic names and offers "Novo paciente" only with patients.manage', async () => {
  server.use(
    ...baseHandlers(READ),
    http.get('/api/v1/patients', () => HttpResponse.json(pageOf([apiPatient()]))),
  )
  const view = renderList()

  const row = (await screen.findByRole('button', { name: 'Rex' })).closest('tr') as HTMLElement
  expect(within(row).getByText('Cão')).toBeInTheDocument()
  expect(within(row).getByText('Maria Souza')).toBeInTheDocument()
  expect(await within(row).findByText('Clínica Central')).toBeInTheDocument()
  expect(within(row).getByText('2 anos')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Novo paciente/i })).not.toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  server.use(
    ...baseHandlers(MANAGE),
    http.get('/api/v1/patients', () => HttpResponse.json(pageOf([apiPatient()]))),
  )
  renderList()
  expect(await screen.findByRole('link', { name: /Novo paciente/i })).toHaveAttribute(
    'href',
    '/pacientes/novo',
  )
})

test('summary cards and status tabs show the server counts', async () => {
  server.use(
    ...baseHandlers(READ, { total: 7, active: 5, inactive: 2 }),
    http.get('/api/v1/patients', () => HttpResponse.json(pageOf([apiPatient()]))),
  )
  renderList()

  const cards = within(await screen.findByRole('region', { name: 'Resumo dos pacientes' }))
  expect(await cards.findByText('7')).toBeInTheDocument()
  expect(cards.getByText('5')).toBeInTheDocument()
  expect(cards.getByText('2')).toBeInTheDocument()
  const tabs = within(screen.getByRole('group', { name: 'Filtrar por status' }))
  expect(await tabs.findByRole('button', { name: /Todos\s*7/ })).toBeInTheDocument()
  expect(tabs.getByRole('button', { name: /Ativos\s*5/ })).toBeInTheDocument()
  expect(tabs.getByRole('button', { name: /Inativos\s*2/ })).toBeInTheDocument()
})

test('search, status tab, clinic and species filters are sent to the server and reset the page', async () => {
  const user = userEvent.setup()
  const listCalls: Record<string, string>[] = []
  const summaryCalls: Record<string, string>[] = []
  server.use(
    meHandler(READ),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/summary', ({ request }) => {
      summaryCalls.push(Object.fromEntries(new URL(request.url).searchParams))
      return HttpResponse.json({ total: 1, active: 1, inactive: 0 })
    }),
    http.get('/api/v1/patients', ({ request }) => {
      listCalls.push(Object.fromEntries(new URL(request.url).searchParams))
      return HttpResponse.json(pageOf([apiPatient()]))
    }),
  )
  renderList()
  await screen.findByRole('button', { name: 'Rex' })

  await user.type(screen.getByLabelText('Buscar paciente'), 'joana')
  await user.click(screen.getByRole('button', { name: /^Clínica/ }))
  await user.click(await screen.findByRole('option', { name: 'Clínica Norte' }))
  await user.click(screen.getByRole('button', { name: /^Espécie/ }))
  await user.click(await screen.findByRole('option', { name: 'Gato' }))
  await user.click(screen.getByRole('button', { name: /Inativos/ }))

  await waitFor(() =>
    expect(listCalls.at(-1)).toMatchObject({
      search: 'joana',
      clinic_id: 'c2',
      species_id: 's2',
      status: 'INACTIVE',
      page: '1',
    }),
  )
  // As abas contam com os mesmos filtros (sem status), para bater com a tabela.
  await waitFor(() =>
    expect(summaryCalls.at(-1)).toMatchObject({
      search: 'joana',
      clinic_id: 'c2',
      species_id: 's2',
    }),
  )
  expect(summaryCalls.at(-1)).not.toHaveProperty('status')
  // Os cartões contam só com a busca: existe uma chamada sem clínica nem espécie.
  expect(
    summaryCalls.some(
      (call) => call.search === 'joana' && !('clinic_id' in call) && !('species_id' in call),
    ),
  ).toBe(true)

  await user.click(screen.getByRole('button', { name: /Limpar filtros/ }))
  await waitFor(() => {
    const last = listCalls.at(-1)
    expect(last).not.toHaveProperty('clinic_id')
    expect(last).not.toHaveProperty('species_id')
    expect(last).toMatchObject({ search: 'joana', status: 'INACTIVE' })
  })
})

test('row click opens the summary popover with the patient, the owner and a link to the patient page', async () => {
  const user = userEvent.setup()
  server.use(
    ...baseHandlers(READ),
    http.get('/api/v1/patients', () => HttpResponse.json(pageOf([apiPatient()]))),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(apiPatient())),
  )
  renderList()

  await user.click(await screen.findByRole('button', { name: 'Rex' }))
  const summary = within(await screen.findByRole('dialog'))
  expect(await summary.findByText('(47) 99999-0000')).toBeInTheDocument()
  expect(summary.getByText('Maria Souza')).toBeInTheDocument()
  expect(summary.getByText('SRD')).toBeInTheDocument()
  expect(summary.getByText('Macho')).toBeInTheDocument()
  expect(summary.getByRole('link', { name: 'Abrir paciente' })).toHaveAttribute(
    'href',
    '/pacientes/p1',
  )
  // Sem patients.manage não há menu de ações.
  expect(summary.queryByRole('button', { name: 'Mais ações' })).not.toBeInTheDocument()

  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

test('with patients.manage the row menu inactivates and reactivates, and counts refresh', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'ACTIVE'
  const calls: string[] = []
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/summary', () =>
      HttpResponse.json(
        status === 'ACTIVE'
          ? { total: 1, active: 1, inactive: 0 }
          : { total: 1, active: 0, inactive: 1 },
      ),
    ),
    http.get('/api/v1/patients', () => HttpResponse.json(pageOf([apiPatient({ status })]))),
    http.post('/api/v1/patients/p1/deactivate', () => {
      calls.push('deactivate')
      status = 'INACTIVE'
      return HttpResponse.json(apiPatient({ status }))
    }),
    http.post('/api/v1/patients/p1/reactivate', () => {
      calls.push('reactivate')
      status = 'ACTIVE'
      return HttpResponse.json(apiPatient({ status }))
    }),
  )
  renderList()

  await user.click(await screen.findByRole('button', { name: 'Ações para Rex' }))
  await user.click(await screen.findByRole('menuitem', { name: 'Inativar paciente' }))
  await waitFor(() => expect(calls).toEqual(['deactivate']))
  const cards = within(screen.getByRole('region', { name: 'Resumo dos pacientes' }))
  await waitFor(() =>
    expect(cards.getByText('Inativos').closest('article')).toHaveTextContent('1'),
  )
  expect(await screen.findByText('Inativo', { selector: '.badge' })).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Ações para Rex' }))
  await user.click(await screen.findByRole('menuitem', { name: 'Reativar paciente' }))
  await waitFor(() => expect(calls).toEqual(['deactivate', 'reactivate']))
  expect(await screen.findByText('Ativo', { selector: '.badge' })).toBeInTheDocument()
})

test('shows the empty, error and permission states', async () => {
  server.use(
    ...baseHandlers(READ),
    http.get('/api/v1/patients', () => HttpResponse.json(pageOf([]))),
  )
  const empty = renderList()
  expect(
    await screen.findByText('Nenhum paciente encontrado para os filtros selecionados.'),
  ).toBeInTheDocument()
  empty.unmount()
  server.resetHandlers()

  server.use(
    ...baseHandlers(READ),
    http.get('/api/v1/patients', () => HttpResponse.json({}, { status: 500 })),
  )
  const failed = renderList()
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Não foi possível carregar os pacientes.',
  )
  expect(screen.queryByText(/Nenhum paciente encontrado/)).not.toBeInTheDocument()
  failed.unmount()
  server.resetHandlers()

  server.use(
    ...baseHandlers(READ),
    http.get('/api/v1/patients', () =>
      HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'x' } }, { status: 403 }),
    ),
  )
  renderList()
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Você não tem permissão para ver pacientes.',
  )
})

test('the popover menu inactivates the patient, stays open with the new status, and closes by x and by backdrop', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'ACTIVE'
  server.use(
    ...baseHandlers(MANAGE),
    http.get('/api/v1/patients', () => HttpResponse.json(pageOf([apiPatient({ status })]))),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(apiPatient({ status }))),
    http.post('/api/v1/patients/p1/deactivate', () => {
      status = 'INACTIVE'
      return HttpResponse.json(apiPatient({ status }))
    }),
  )
  renderList()

  await user.click(await screen.findByRole('button', { name: 'Rex' }))
  const dialog = within(await screen.findByRole('dialog'))
  await user.click(await dialog.findByRole('button', { name: 'Mais ações' }))
  await user.click(await screen.findByRole('menuitem', { name: 'Inativar paciente' }))
  expect(await dialog.findByText('Inativo')).toBeInTheDocument()
  await user.click(dialog.getByRole('button', { name: 'Mais ações' }))
  expect(await screen.findByRole('menuitem', { name: 'Reativar paciente' })).toBeInTheDocument()
  await user.keyboard('{Escape}')

  await user.click(dialog.getByRole('button', { name: 'Fechar resumo' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

  await user.click(screen.getByRole('button', { name: 'Rex' }))
  await screen.findByRole('dialog')
  await user.click(document.querySelector('.modal__backdrop') as HTMLElement)
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

test('the popover says when the patient cannot be shown because of permission', async () => {
  const user = userEvent.setup()
  server.use(
    ...baseHandlers(READ),
    http.get('/api/v1/patients', () => HttpResponse.json(pageOf([apiPatient()]))),
    http.get('/api/v1/patients/p1', () =>
      HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'x' } }, { status: 403 }),
    ),
  )
  renderList()

  await user.click(await screen.findByRole('button', { name: 'Rex' }))
  expect(
    await within(await screen.findByRole('dialog')).findByText(
      'Você não tem permissão para ver este paciente.',
    ),
  ).toBeInTheDocument()
})

