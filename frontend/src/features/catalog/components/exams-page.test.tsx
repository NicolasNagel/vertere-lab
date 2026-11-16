import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
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
          is_panel: false,
          component_exam_ids: [],
          price_base: '85.00',
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
          is_panel: false,
          component_exam_ids: [],
          price_base: '120.00',
          updated_at: '2026-06-02T00:00:00Z',
        },
      ],
      total: 2,
      page: 1,
      page_size: 100,
    }),
  )
}

function renderWithProviders(
  children: ReactNode,
  initialEntries: string[] = ['/cadastros/exames'],
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
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
      <Route path="/cadastros/exames/:examId" element={<p>Detalhe do exame</p>} />
    </Routes>,
    initialEntries,
  )
}

// Cada fase reinicia a árvore e os handlers do MSW para não herdar resposta da anterior.
function restart(view: ReturnType<typeof renderApp>) {
  view.unmount()
  server.resetHandlers()
}

const hemogramaExam = {
  id: 'e1',
  code: 'HEM001',
  name: 'Hemograma completo',
  category_id: 'cat1',
  description: 'Eritograma + Leucograma',
  species_ids: ['s1'],
  status: 'ACTIVE',
  row_version: 1,
  is_panel: false,
  component_exam_ids: [],
  price_base: '85.00',
  updated_at: '2026-06-01T00:00:00Z',
}

test('lists exams, filters by category and gates actions and prices by permission', async () => {
  const user = userEvent.setup()
  const common = [speciesHandler(), categoriesHandler(), examsListHandler()]

  // Só catalog.read: lista, filtro por categoria, sem ação de gestão nem preço/ticket.
  server.use(meHandler(['catalog.read']), ...common)
  let view = renderApp()
  expect(await screen.findByText('Hemograma completo')).toBeInTheDocument()
  expect(screen.getByText('HEM001')).toBeInTheDocument()
  expect(screen.getByText('Bioquímico renal')).toBeInTheDocument()
  expect(screen.queryByText(/Novo exame/i)).not.toBeInTheDocument()
  expect(screen.queryByText('R$ 85,00')).not.toBeInTheDocument()
  const requested: string[] = []
  server.use(
    http.get('/api/v1/exams', ({ request }) => {
      requested.push(new URL(request.url).search)
      return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25 })
    }),
  )
  await user.click(await screen.findByRole('button', { name: /Categoria/ }))
  await user.click(await screen.findByRole('option', { name: 'Bioquímica' }))
  await waitFor(() =>
    expect(requested.some((query) => query.includes('category_id=cat2'))).toBe(true),
  )
  expect(await screen.findByText(/Nenhum exame encontrado/)).toBeInTheDocument()
  restart(view)

  // catalog.manage libera "Novo exame".
  server.use(meHandler(['catalog.read', 'catalog.manage']), ...common)
  view = renderApp()
  expect(await screen.findByText(/Novo pacote/i)).toBeInTheDocument()
  expect(screen.queryByText(/Novo exame/i)).not.toBeInTheDocument()
  restart(view)

  // Criar exame também exige pricing.manage (define o preço).
  server.use(meHandler(['catalog.read', 'catalog.manage', 'pricing.manage']), ...common)
  view = renderApp()
  expect(await screen.findByText(/Novo exame/i)).toBeInTheDocument()
  restart(view)

  // pricing.read mostra os preços.
  server.use(meHandler(['catalog.read', 'pricing.read']), ...common)
  view = renderApp()
  expect(await screen.findByText('R$ 85,00')).toBeInTheDocument()
  restart(view)
})

test('a manager imports exams from CSV with per-row errors and opens a row in the detail route', async () => {
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
    http.get('/api/v1/exams/e1', () => HttpResponse.json(hemogramaExam)),
  )
  const user = userEvent.setup()
  renderApp()

  await screen.findByText('Hemograma completo')
  const file = new File(['code,name\nA,B\n'], 'exams.csv', {
    type: 'text/csv',
  })
  await user.upload(screen.getByLabelText('Selecionar arquivo CSV para importar exames'), file)
  expect(await screen.findByText('1 exame(s) importado(s) com sucesso.')).toBeInTheDocument()
  expect(screen.getByText(/Linha 3: Categoria 'Inexistente' não encontrada\./)).toBeInTheDocument()

  await user.click(screen.getByText('Hemograma completo'))
  const summary = within(await screen.findByRole('dialog', { name: 'Hemograma completo' }))
  expect(summary.getByText('Hematologia')).toBeInTheDocument()
  await user.click(summary.getByRole('link', { name: 'Abrir exame' }))
  expect(await screen.findByText('Detalhe do exame')).toBeInTheDocument()
})

test('the summary popover is read-only for users without catalog.manage and closes with Escape', async () => {
  server.use(meHandler(['catalog.read']), speciesHandler(), categoriesHandler(), examsListHandler())
  const user = userEvent.setup()
  renderApp()

  await user.click(await screen.findByText('Hemograma completo'))
  const summary = within(await screen.findByRole('dialog', { name: 'Hemograma completo' }))
  expect(summary.getByRole('link', { name: 'Abrir exame' })).toBeInTheDocument()
  expect(summary.queryByRole('link', { name: 'Editar exame' })).not.toBeInTheDocument()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

test('the fees tab shows the fee registers (plantão, urgência, por clínica) instead of the exam table', async () => {
  server.use(
    meHandler(['catalog.read', 'pricing.read']),
    speciesHandler(),
    categoriesHandler(),
    examsListHandler(),
    http.get('/api/v1/on-call-fee-settings', () => HttpResponse.json({ items: [] })),
  )
  const user = userEvent.setup()
  renderApp()

  await screen.findByText('Hemograma completo')
  expect(screen.getByRole('tab', { name: 'Urgência' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Por clínica' })).toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: 'Plantão' }))
  expect(screen.queryByText('Hemograma completo')).not.toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Plantão' })).toHaveAttribute('aria-selected', 'true')
})

test('deactivating an exam from the row menu calls the API', async () => {
  let item = { ...hemogramaExam }
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
  const row = screen.getByText('Hemograma completo').closest('tr')
  expect(row).not.toBeNull()
  await user.click(within(row as HTMLElement).getByRole('button', { name: /Ações para/i }))
  await user.click(await screen.findByRole('menuitem', { name: 'Inativar' }))

  await waitFor(() => expect(screen.getByText('Inativo')).toBeInTheDocument())
})
