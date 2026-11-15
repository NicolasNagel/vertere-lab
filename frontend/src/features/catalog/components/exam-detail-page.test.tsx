import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
import { ExamDetailPage } from './exam-detail-page'

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

const examBody = {
  id: 'e1',
  code: 'HEM001',
  name: 'Hemograma completo',
  category_id: 'cat1',
  description: null,
  species_ids: ['s1'],
  component_exam_ids: [],
  is_panel: false,
  status: 'ACTIVE',
  row_version: 3,
  price_base: '85.00',
  price_valid_from: '2026-01-01',
  price_valid_to: null,
  updated_at: '2026-06-01T00:00:00Z',
}

function commonHandlers(exam: Record<string, unknown> = examBody) {
  return [
    http.get('/api/v1/exams/e1', () => HttpResponse.json(exam)),
    http.get('/api/v1/species', () =>
      HttpResponse.json({ items: [{ id: 's1', name: 'Cão', created_at: '2026-01-01T00:00:00Z' }] }),
    ),
    http.get('/api/v1/exam-categories/active', () =>
      HttpResponse.json({
        items: [{ id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 }],
      }),
    ),
  ]
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={['/cadastros/exames/e1']}>
          <Routes>
            <Route path="/cadastros/exames/:examId" element={<ExamDetailPage />} />
            <Route path="/cadastros/exames" element={<p>Lista de exames</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('shows the blocks, hides price without pricing.read and has no edit without catalog.manage', async () => {
  server.use(
    meHandler(['catalog.read']),
    ...commonHandlers({ ...examBody, price_base: null, price_valid_from: null }),
  )
  renderPage()

  expect(await screen.findByRole('heading', { name: 'Identificação' })).toBeInTheDocument()
  expect(screen.getByText('Hematologia')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Preço e vigência' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Editar/ })).not.toBeInTheDocument()
})

test('price block is read-only without pricing.manage but editable blocks still are', async () => {
  server.use(meHandler(['catalog.read', 'catalog.manage', 'pricing.read']), ...commonHandlers())
  renderPage()

  expect((await screen.findAllByText('R$ 85,00')).length).toBeGreaterThan(0)
  expect(screen.getByRole('region', { name: 'Resumo do exame' })).toBeInTheDocument()
  expect(screen.getByText(/Alterar preço exige a permissão/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Editar preço e vigência' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Editar status' })).toBeInTheDocument()
})

test('saving needs a reason, sends it with the row version and omits the price without pricing.manage', async () => {
  const user = userEvent.setup()
  let sent: Record<string, unknown> | null = null
  server.use(
    meHandler(['catalog.read', 'catalog.manage', 'pricing.read']),
    ...commonHandlers(),
    http.patch('/api/v1/exams/e1', async ({ request }) => {
      sent = (await request.json()) as Record<string, unknown>
      return HttpResponse.json({ ...examBody, status: 'INACTIVE', row_version: 4 })
    }),
  )
  renderPage()

  await user.click(await screen.findByRole('button', { name: 'Editar status' }))
  await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'INACTIVE')
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()

  await user.type(screen.getByLabelText('Motivo da alteração'), 'Exame descontinuado')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(sent).not.toBeNull())
  expect(sent).toMatchObject({
    status: 'INACTIVE',
    reason: 'Exame descontinuado',
    expected_row_version: 3,
    name: 'Hemograma completo',
  })
  expect(sent).not.toHaveProperty('price_base')
})

test('a version conflict shows the message and offers to reload', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['catalog.read', 'catalog.manage', 'pricing.read', 'pricing.manage']),
    ...commonHandlers(),
    http.patch('/api/v1/exams/e1', () =>
      HttpResponse.json(
        { error: { code: 'CONFLICT', message: 'Este exame foi alterado por outra pessoa.' } },
        { status: 409 },
      ),
    ),
  )
  renderPage()

  await user.click(await screen.findByRole('button', { name: 'Editar preço e vigência' }))
  const price = screen.getByLabelText('Preço base')
  await user.clear(price)
  await user.type(price, '90')
  await user.type(screen.getByLabelText('Motivo da alteração'), 'Reajuste')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('alterado por outra pessoa')
  expect(screen.getByRole('button', { name: 'Recarregar exame' })).toBeInTheDocument()
})

test('shows an error state when the exam cannot be loaded and a 403 message without access', async () => {
  server.use(
    meHandler(['catalog.read']),
    http.get('/api/v1/exams/e1', () =>
      HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'Sem acesso.' } }, { status: 403 }),
    ),
    ...commonHandlers(),
  )
  renderPage()

  expect(await screen.findByRole('alert')).toHaveTextContent('Você não tem permissão para visualizar este exame.')
})
