import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { ExamFormPage } from './exam-form-page'
import { ExamsPage } from './exams-page'

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

function speciesHandler() {
  return http.get('/api/v1/species', () =>
    HttpResponse.json({
      items: [
        { id: 's1', name: 'Cão', created_at: '2026-01-01T00:00:00Z' },
        { id: 's2', name: 'Gato', created_at: '2026-01-01T00:00:00Z' },
      ],
    }),
  )
}

function categoriesHandler() {
  return http.get('/api/v1/exam-categories/active', () =>
    HttpResponse.json({
      items: [
        { id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 },
        { id: 'cat2', name: 'Bioquímica', status: 'ACTIVE', row_version: 1 },
      ],
    }),
  )
}

function examsListHandler() {
  return http.get('/api/v1/exams', () =>
    HttpResponse.json({
      items: [
        {
          id: 'e1',
          code: 'HEM001',
          name: 'Hemograma completo',
          category_id: 'cat1',
          description: 'Eritograma + Leucograma',
          species_ids: ['s1'],
          status: 'ACTIVE',
          row_version: 1,
          price_base: '85.00',
          plantao_surcharge_fixed: null,
          plantao_surcharge_percent: '20.00',
          updated_at: '2026-06-01T00:00:00Z',
        },
        {
          id: 'e2',
          code: 'BIO001',
          name: 'Bioquímico renal',
          category_id: 'cat2',
          description: null,
          species_ids: ['s1', 's2'],
          status: 'ACTIVE',
          row_version: 1,
          price_base: '120.00',
          plantao_surcharge_fixed: null,
          plantao_surcharge_percent: null,
          updated_at: '2026-06-02T00:00:00Z',
        },
      ],
      total: 2,
      page: 1,
      page_size: 100,
    }),
  )
}

function renderWithProviders(children: ReactNode, initialEntries: string[] = ['/cadastros/exames']) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

function renderApp(initialEntries: string[] = ['/cadastros/exames']) {
  return renderWithProviders(
    <Routes>
      <Route path="/cadastros/exames" element={<ExamsPage />} />
      <Route path="/cadastros/exames/novo" element={<ExamFormPage />} />
      <Route path="/cadastros/exames/:examId/editar" element={<ExamFormPage />} />
    </Routes>,
    initialEntries,
  )
}

test('lists exams returned by the API', async () => {
  server.use(meHandler(['catalog.read']), speciesHandler(), categoriesHandler(), examsListHandler())
  renderApp()

  expect(await screen.findByText('Hemograma completo')).toBeInTheDocument()
  expect(screen.getByText('HEM001')).toBeInTheDocument()
  expect(screen.getByText('Bioquímico renal')).toBeInTheDocument()
})

test('hides management actions for a user without catalog.manage', async () => {
  server.use(meHandler(['catalog.read']), speciesHandler(), categoriesHandler(), examsListHandler())
  renderApp()

  await screen.findByText('Hemograma completo')
  expect(screen.queryByRole('button', { name: /Novo exame/i })).not.toBeInTheDocument()
})

test('shows the "Novo exame" action for a user with catalog.manage', async () => {
  server.use(
    meHandler(['catalog.read', 'catalog.manage']),
    speciesHandler(),
    categoriesHandler(),
    examsListHandler(),
  )
  renderApp()

  expect(await screen.findByRole('button', { name: /Novo exame/i })).toBeInTheDocument()
})

test('hides price columns and the average-ticket card without pricing.read', async () => {
  server.use(meHandler(['catalog.read']), speciesHandler(), categoriesHandler(), examsListHandler())
  renderApp()

  await screen.findByText('Hemograma completo')
  expect(screen.queryByText('R$ 85.00')).not.toBeInTheDocument()
  expect(screen.queryByText('Ticket médio')).not.toBeInTheDocument()
})

test('shows price columns with pricing.read', async () => {
  server.use(
    meHandler(['catalog.read', 'pricing.read']),
    speciesHandler(),
    categoriesHandler(),
    examsListHandler(),
  )
  renderApp()

  expect(await screen.findByText('R$ 85.00')).toBeInTheDocument()
  expect(screen.getByText('Ticket médio')).toBeInTheDocument()
})

test('average ticket excludes inactive exams from the calculation', async () => {
  server.use(
    meHandler(['catalog.read', 'pricing.read']),
    speciesHandler(),
    categoriesHandler(),
    http.get('/api/v1/exams', () =>
      HttpResponse.json({
        items: [
          {
            id: 'e1',
            code: 'HEM001',
            name: 'Hemograma completo',
            category_id: 'cat1',
            description: null,
            species_ids: ['s1'],
            status: 'INACTIVE',
            row_version: 2,
            price_base: '85.00',
            plantao_surcharge_fixed: null,
            plantao_surcharge_percent: null,
            updated_at: '2026-06-01T00:00:00Z',
          },
          {
            id: 'e2',
            code: 'BIO001',
            name: 'Bioquímico renal',
            category_id: 'cat2',
            description: null,
            species_ids: ['s1'],
            status: 'ACTIVE',
            row_version: 1,
            price_base: '120.00',
            plantao_surcharge_fixed: null,
            plantao_surcharge_percent: null,
            updated_at: '2026-06-02T00:00:00Z',
          },
        ],
        total: 2,
        page: 1,
        page_size: 100,
      }),
    ),
  )
  renderApp()

  await screen.findByText('Bioquímico renal')
  expect(await screen.findByText('R$ 120,00')).toBeInTheDocument()
})

test('filtering by category shows only exams in that category', async () => {
  server.use(meHandler(['catalog.read']), speciesHandler(), categoriesHandler(), examsListHandler())
  const user = userEvent.setup()
  renderApp()

  await screen.findByText('Hemograma completo')
  await user.click(screen.getByRole('button', { name: /Bioquímica/ }))

  expect(screen.queryByText('Hemograma completo')).not.toBeInTheDocument()
  expect(screen.getByText('Bioquímico renal')).toBeInTheDocument()
})

test('clicking a row navigates to the edit route for a manager', async () => {
  server.use(
    meHandler(['catalog.read', 'catalog.manage']),
    speciesHandler(),
    categoriesHandler(),
    examsListHandler(),
    http.get('/api/v1/exams/e1', () =>
      HttpResponse.json({
        id: 'e1',
        code: 'HEM001',
        name: 'Hemograma completo',
        category_id: 'cat1',
        description: 'Eritograma + Leucograma',
        species_ids: ['s1'],
        status: 'ACTIVE',
        row_version: 1,
        price_base: '85.00',
        plantao_surcharge_fixed: null,
        plantao_surcharge_percent: '20.00',
        updated_at: '2026-06-01T00:00:00Z',
      }),
    ),
  )
  const user = userEvent.setup()
  renderApp()

  await user.click(await screen.findByText('Hemograma completo'))

  expect(await screen.findByRole('heading', { name: 'Editar exame' })).toBeInTheDocument()
  expect(await screen.findByDisplayValue('HEM001')).toBeInTheDocument()
})

test('imports exams from CSV and reports per-row errors', async () => {
  server.use(
    meHandler(['catalog.read', 'catalog.manage']),
    speciesHandler(),
    categoriesHandler(),
    examsListHandler(),
    http.post('/api/v1/exams/import', () =>
      HttpResponse.json({
        imported_count: 1,
        errors: [{ line: 3, message: "Categoria 'Inexistente' não encontrada." }],
      }),
    ),
  )
  const user = userEvent.setup()
  renderApp()

  await screen.findByText('Hemograma completo')
  const file = new File(['code,name\nA,B\n'], 'exams.csv', { type: 'text/csv' })
  const input = screen.getByLabelText('Selecionar arquivo CSV para importar exames')
  await user.upload(input, file)

  expect(await screen.findByText('1 exame(s) importado(s) com sucesso.')).toBeInTheDocument()
  expect(screen.getByText(/Linha 3: Categoria 'Inexistente' não encontrada\./)).toBeInTheDocument()
})

interface MockApiExam {
  id: string
  code: string
  name: string
  category_id: string
  description: string | null
  species_ids: string[]
  status: string
  row_version: number
  price_base: string | null
  plantao_surcharge_fixed: string | null
  plantao_surcharge_percent: string | null
  updated_at: string
}

test('deactivating an exam from the row menu calls the API', async () => {
  let item: MockApiExam = {
    id: 'e1',
    code: 'HEM001',
    name: 'Hemograma completo',
    category_id: 'cat1',
    description: 'Eritograma + Leucograma',
    species_ids: ['s1'],
    status: 'ACTIVE',
    row_version: 1,
    price_base: '85.00',
    plantao_surcharge_fixed: null,
    plantao_surcharge_percent: '20.00',
    updated_at: '2026-06-01T00:00:00Z',
  }
  server.use(
    meHandler(['catalog.read', 'catalog.manage']),
    speciesHandler(),
    categoriesHandler(),
    http.get('/api/v1/exams', () =>
      HttpResponse.json({ items: [item], total: 1, page: 1, page_size: 100 }),
    ),
    http.post('/api/v1/exams/e1/deactivate', () => {
      item = { ...item, status: 'INACTIVE', row_version: 2 }
      return HttpResponse.json(item)
    }),
  )
  const user = userEvent.setup()
  renderApp()

  await screen.findByText('Hemograma completo')
  const row = screen.getByText('Hemograma completo').closest('[role="button"]')
  expect(row).not.toBeNull()
  await user.click(within(row as HTMLElement).getByRole('button', { name: /Ações para/i }))
  await user.click(await screen.findByRole('menuitem', { name: 'Inativar' }))

  await waitFor(() => expect(screen.getByText('Inativo')).toBeInTheDocument())
})
