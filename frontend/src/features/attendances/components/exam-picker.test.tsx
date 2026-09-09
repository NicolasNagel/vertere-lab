import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'

import { ExamPicker } from './exam-picker'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function exam(name: string, code: string) {
  return {
    id: code,
    code,
    name,
    category_id: 'category-1',
    description: null,
    species_ids: ['species-1'],
    status: 'ACTIVE',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    row_version: 1,
    price_base: '50.00',
    price_valid_from: '2026-01-01',
    price_valid_to: null,
  }
}

function renderPicker({ disabled = false }: { disabled?: boolean } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const onSelect = vi.fn()
  render(
    <QueryClientProvider client={queryClient}>
      <ExamPicker disabled={disabled} excludeExamIds={[]} onSelect={onSelect} />
    </QueryClientProvider>,
  )
  return onSelect
}

test('loads active exams before the user types', async () => {
  server.use(
    http.get('/api/v1/exams', ({ request }) => {
      const query = new URL(request.url).searchParams
      expect(query.get('status')).toBe('ACTIVE')
      expect(query.has('search')).toBe(false)
      return HttpResponse.json({
        items: [exam('Hemograma', 'A1B2C3D4')],
        total: 1,
        page: 1,
        page_size: 10,
      })
    }),
  )
  const onSelect = renderPicker()

  await userEvent.click(await screen.findByRole('option', { name: /Hemograma/ }))

  expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ code: 'A1B2C3D4' }))
})

test('searches by the typed name after debounce', async () => {
  server.use(
    http.get('/api/v1/exams', ({ request }) => {
      const search = new URL(request.url).searchParams.get('search')
      return HttpResponse.json({
        items: search ? [exam('Urinálise', 'U1R2I3N4')] : [],
        total: search ? 1 : 0,
        page: 1,
        page_size: 10,
      })
    }),
  )
  renderPicker()

  await userEvent.type(screen.getByLabelText('Adicionar exame'), 'urina')

  expect(await screen.findByText('Urinálise')).toBeInTheDocument()
})

test('offers a retry when loading exams fails', async () => {
  let attempts = 0
  server.use(
    http.get('/api/v1/exams', () => {
      attempts += 1
      if (attempts === 1) return HttpResponse.json({}, { status: 500 })
      return HttpResponse.json({
        items: [exam('Hemograma', 'A1B2C3D4')],
        total: 1,
        page: 1,
        page_size: 10,
      })
    }),
  )
  renderPicker()

  await userEvent.click(await screen.findByRole('button', { name: 'Tentar novamente' }))

  expect(await screen.findByText('Hemograma')).toBeInTheDocument()
})

test('prevents selecting a loaded exam while disabled', async () => {
  server.use(
    http.get('/api/v1/exams', () =>
      HttpResponse.json({
        items: [exam('Hemograma', 'A1B2C3D4')],
        total: 1,
        page: 1,
        page_size: 10,
      }),
    ),
  )
  const onSelect = renderPicker({ disabled: true })

  const option = await screen.findByRole('option', { name: /Hemograma/ })

  expect(option).toBeDisabled()
  await userEvent.click(option)
  expect(onSelect).not.toHaveBeenCalled()
})
