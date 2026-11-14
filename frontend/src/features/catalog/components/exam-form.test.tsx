import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'

import type { Exam } from '../api/catalog-api'
import { ExamForm } from './exam-form'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function speciesHandler() {
  return http.get('/api/v1/species', () =>
    HttpResponse.json({
      items: [{ id: 's1', name: 'Cão', created_at: '2026-01-01T00:00:00Z' }],
    }),
  )
}

const existingExam: Exam = {
  id: 'e1',
  code: 'HEM001',
  name: 'Hemograma completo',
  categoryId: 'cat-inactive',
  description: null,
  speciesIds: ['s1'],
  componentExamIds: [],
  isPanel: false,
  status: 'ACTIVE',
  rowVersion: 1,
  priceBase: '85.00',
  updatedAt: '2026-01-01T00:00:00Z',
}

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>)
}

test('editing an exam whose category was deactivated still shows and retains that category', async () => {
  server.use(
    speciesHandler(),
    // active list does NOT include the exam's category — it was deactivated
    http.get('/api/v1/exam-categories/active', () =>
      HttpResponse.json({ items: [{ id: 'cat-active', name: 'Bioquímica', status: 'ACTIVE', row_version: 1 }] }),
    ),
    http.get('/api/v1/exam-categories/cat-inactive', () =>
      HttpResponse.json({
        id: 'cat-inactive',
        name: 'Hematologia',
        status: 'INACTIVE',
        row_version: 1,
      }),
    ),
  )
  const onSubmitUpdate = vi.fn()
  renderWithProviders(
    <ExamForm
      exam={existingExam}
      submitting={false}
      onCancel={() => {}}
      onSubmitUpdate={onSubmitUpdate}
    />,
  )

  const select = await screen.findByLabelText<HTMLSelectElement>('Categoria')
  await waitFor(() => expect(select).toHaveValue('cat-inactive'))
  expect(screen.getByText('Hematologia (inativa)')).toBeInTheDocument()

  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(onSubmitUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ categoryId: 'cat-inactive' }),
    ),
  )
})

test('creating a category inline selects it once the refetched list includes it', async () => {
  let categories = [{ id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 }]
  server.use(
    speciesHandler(),
    http.get('/api/v1/exam-categories/active', () => HttpResponse.json({ items: categories })),
    http.post('/api/v1/exam-categories', async ({ request }) => {
      const body = (await request.json()) as { name: string }
      const created = { id: 'cat2', name: body.name, status: 'ACTIVE' as const, row_version: 1 }
      categories = [...categories, created]
      return HttpResponse.json(created, { status: 201 })
    }),
  )
  const user = userEvent.setup()
  renderWithProviders(
    <ExamForm exam={null} submitting={false} onCancel={() => {}} onSubmitCreate={() => {}} />,
  )

  await user.type(await screen.findByLabelText('Criar nova categoria'), 'Bioquímica')
  await user.click(screen.getByRole('button', { name: 'Criar categoria' }))

  await waitFor(() =>
    expect(screen.getByLabelText<HTMLSelectElement>('Categoria')).toHaveValue('cat2'),
  )
})

function apiExam(id: string, name: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    code: `COD${id.toUpperCase()}`,
    name,
    category_id: 'cat1',
    description: null,
    species_ids: ['s1'],
    component_exam_ids: [],
    is_panel: false,
    status: 'ACTIVE',
    row_version: 1,
    price_base: '20.00',
    price_valid_from: null,
    price_valid_to: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

test('a new panel needs at least 2 exams and submits them in the chosen order', async () => {
  const exams = [
    apiExam('a', 'Hemograma'),
    apiExam('b', 'ALT'),
    apiExam('p', 'CHECK-UP', { is_panel: true, component_exam_ids: ['a', 'b'] }),
  ]
  server.use(
    speciesHandler(),
    http.get('/api/v1/exam-categories/active', () =>
      HttpResponse.json({
        items: [{ id: 'cat1', name: 'Perfis', status: 'ACTIVE', row_version: 1 }],
      }),
    ),
    http.get('/api/v1/exams', () =>
      HttpResponse.json({ items: exams, total: 3, page: 1, page_size: 10 }),
    ),
    http.get('/api/v1/exams/:id', ({ params }) =>
      HttpResponse.json(exams.find((exam) => exam.id === params.id)),
    ),
  )
  const onSubmitCreate = vi.fn()
  const user = userEvent.setup()
  renderWithProviders(
    <ExamForm
      exam={null}
      panel
      submitting={false}
      onCancel={() => {}}
      onSubmitCreate={onSubmitCreate}
    />,
  )

  await user.type(await screen.findByLabelText('Nome do pacote'), 'BÁSICO 1')
  await waitFor(() => expect(screen.getByLabelText('Categoria')).toHaveValue(''))
  await user.selectOptions(screen.getByLabelText('Categoria'), 'cat1')
  await user.type(screen.getByLabelText('Preço do pacote'), '70.00')
  await user.click(await screen.findByLabelText('Cão'))

  // Pacote não aparece como opção (sem aninhar): só Hemograma e ALT.
  expect(await screen.findByRole('option', { name: /Hemograma/ })).toBeInTheDocument()
  expect(screen.queryByRole('option', { name: /CHECK-UP/ })).not.toBeInTheDocument()

  await user.click(screen.getByRole('option', { name: /Hemograma/ }))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  expect(await screen.findByText('Um pacote precisa de ao menos 2 exames.')).toBeInTheDocument()
  expect(onSubmitCreate).not.toHaveBeenCalled()

  await user.click(await screen.findByRole('option', { name: /ALT/ }))
  await user.click(await screen.findByRole('button', { name: 'Subir ALT' }))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(onSubmitCreate).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'BÁSICO 1', componentExamIds: ['b', 'a'] }),
    ),
  )
})
