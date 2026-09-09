import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
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
      user: { id: 'u1', email: 'a@b.com', full_name: 'A', role_id: 'r1', role_name: 'LAB_ADMIN' },
      permissions,
    }),
  )
}

function speciesHandler() {
  return http.get('/api/v1/species', () =>
    HttpResponse.json({
      items: [{ id: 's1', name: 'Gato', created_at: '2026-01-01T00:00:00Z' }],
    }),
  )
}

function categoriesHandler() {
  return http.get('/api/v1/exam-categories/active', () =>
    HttpResponse.json({
      items: [{ id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 }],
    }),
  )
}

function renderApp(initialEntries: string[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>
          <Routes>
            <Route path="/cadastros/exames" element={<ExamsPage />} />
            <Route path="/cadastros/exames/novo" element={<ExamFormPage />} />
            <Route path="/cadastros/exames/:examId/editar" element={<ExamFormPage />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('creates an exam via the header submit button and returns to the list', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['catalog.read', 'catalog.manage']),
    speciesHandler(),
    categoriesHandler(),
    http.get('/api/v1/exams', () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
    ),
    http.post('/api/v1/exams', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      return HttpResponse.json(
        {
          id: 'e2',
          code: 'A1B2C3D4',
          name: body.name,
          category_id: body.category_id,
          description: body.description,
          species_ids: body.species_ids,
          status: 'ACTIVE',
          row_version: 1,
          price_base: body.price_base,
          updated_at: '2026-06-01T00:00:00Z',
        },
        { status: 201 },
      )
    }),
  )
  renderApp(['/cadastros/exames/novo'])

  expect(await screen.findByRole('heading', { name: 'Cadastro de exame' })).toBeInTheDocument()

  expect(screen.getByLabelText('Código')).toHaveValue('Gerado automaticamente ao salvar')
  await user.type(screen.getByLabelText('Nome'), 'Urinálise')
  await user.selectOptions(await screen.findByLabelText('Categoria'), 'Hematologia')
  await user.type(screen.getByLabelText('Preço base'), '40.00')
  await user.click(await screen.findByLabelText('Gato'))
  await user.click(screen.getByRole('button', { name: 'Salvar exame' }))

  expect(await screen.findByRole('heading', { name: 'Exames & Preços' })).toBeInTheDocument()
})

test('cancel button returns to the list without saving', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['catalog.read', 'catalog.manage']),
    speciesHandler(),
    categoriesHandler(),
    http.get('/api/v1/exams', () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
    ),
  )
  renderApp(['/cadastros/exames/novo'])

  await screen.findByRole('heading', { name: 'Cadastro de exame' })
  await user.click(screen.getByRole('button', { name: 'Cancelar' }))

  await waitFor(() =>
    expect(screen.getByRole('heading', { name: 'Exames & Preços' })).toBeInTheDocument(),
  )
})

test('blocks exam creation without at least one species', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['catalog.read', 'catalog.manage']),
    speciesHandler(),
    categoriesHandler(),
    http.get('/api/v1/exams', () =>
      HttpResponse.json({ items: [], total: 0, page: 1, page_size: 100 }),
    ),
  )
  renderApp(['/cadastros/exames/novo'])

  await user.type(screen.getByLabelText('Nome'), 'Urinálise')
  await user.selectOptions(await screen.findByLabelText('Categoria'), 'Hematologia')
  await user.type(screen.getByLabelText('Preço base'), '40.00')
  await user.click(screen.getByRole('button', { name: 'Salvar exame' }))

  expect(
    await screen.findByText('Selecione ao menos uma espécie atendida.'),
  ).toBeInTheDocument()
})
