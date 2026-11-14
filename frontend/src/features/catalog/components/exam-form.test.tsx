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
