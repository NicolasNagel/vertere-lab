import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { ReactNode } from 'react'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { AuthProvider } from '../../auth/auth-provider'
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
      items: [{ id: 'cat1', name: 'Hematologia', status: 'ACTIVE', row_version: 1 }],
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
          description: null,
          species_ids: ['s1'],
          status: 'ACTIVE',
          row_version: 1,
          price_base: '85.00',
          plantao_surcharge_fixed: null,
          plantao_surcharge_percent: '20.00',
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
    }),
  )
}

function renderWithProviders(children: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>,
  )
}

test('lists exams returned by the API', async () => {
  server.use(meHandler(['catalog.read']), speciesHandler(), categoriesHandler(), examsListHandler())
  renderWithProviders(<ExamsPage />)

  expect(await screen.findByText('Hemograma completo')).toBeInTheDocument()
  expect(screen.getByText('HEM001')).toBeInTheDocument()
})

test('hides the "Novo exame" action for a user without catalog.manage', async () => {
  server.use(meHandler(['catalog.read']), speciesHandler(), categoriesHandler(), examsListHandler())
  renderWithProviders(<ExamsPage />)

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
  renderWithProviders(<ExamsPage />)

  expect(await screen.findByRole('button', { name: /Novo exame/i })).toBeInTheDocument()
})

test('exam detail shows the price when pricing.read is granted', async () => {
  server.use(
    meHandler(['catalog.read', 'pricing.read']),
    speciesHandler(),
    categoriesHandler(),
    examsListHandler(),
    http.get('/api/v1/exams/e1', () =>
      HttpResponse.json({
        id: 'e1',
        code: 'HEM001',
        name: 'Hemograma completo',
        category_id: 'cat1',
        description: null,
        species_ids: ['s1'],
        status: 'ACTIVE',
        row_version: 1,
        price_base: '85.00',
        plantao_surcharge_fixed: null,
        plantao_surcharge_percent: '20.00',
      }),
    ),
  )
  const user = userEvent.setup()
  renderWithProviders(<ExamsPage />)

  await user.click(await screen.findByText('Hemograma completo'))

  expect(await screen.findByText('85.00')).toBeInTheDocument()
})

test('exam detail hides the price when pricing.read is missing', async () => {
  server.use(
    meHandler(['catalog.read']),
    speciesHandler(),
    categoriesHandler(),
    examsListHandler(),
    http.get('/api/v1/exams/e1', () =>
      HttpResponse.json({
        id: 'e1',
        code: 'HEM001',
        name: 'Hemograma completo',
        category_id: 'cat1',
        description: null,
        species_ids: ['s1'],
        status: 'ACTIVE',
        row_version: 1,
        price_base: null,
        plantao_surcharge_fixed: null,
        plantao_surcharge_percent: null,
      }),
    ),
  )
  const user = userEvent.setup()
  renderWithProviders(<ExamsPage />)

  await user.click(await screen.findByText('Hemograma completo'))

  expect(
    await screen.findByText('Você não tem permissão para visualizar valores.'),
  ).toBeInTheDocument()
})

test('creates an exam and returns to the detail view', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['catalog.read', 'catalog.manage']),
    speciesHandler(),
    categoriesHandler(),
    examsListHandler(),
    http.post('/api/v1/exams', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      return HttpResponse.json(
        {
          id: 'e2',
          code: body.code,
          name: body.name,
          category_id: body.category_id,
          description: body.description,
          species_ids: body.species_ids,
          status: 'ACTIVE',
          row_version: 1,
          price_base: body.price_base,
          plantao_surcharge_fixed: body.plantao_surcharge_fixed,
          plantao_surcharge_percent: body.plantao_surcharge_percent,
        },
        { status: 201 },
      )
    }),
    http.get('/api/v1/exams/e2', () =>
      HttpResponse.json({
        id: 'e2',
        code: 'URI001',
        name: 'Urinálise',
        category_id: 'cat1',
        description: null,
        species_ids: ['s2'],
        status: 'ACTIVE',
        row_version: 1,
        price_base: '40.00',
        plantao_surcharge_fixed: null,
        plantao_surcharge_percent: null,
      }),
    ),
  )
  renderWithProviders(<ExamsPage />)

  await user.click(await screen.findByRole('button', { name: /Novo exame/i }))
  await user.type(screen.getByLabelText('Código'), 'URI001')
  await user.type(screen.getByLabelText('Nome'), 'Urinálise')
  await user.selectOptions(await screen.findByLabelText('Categoria'), 'Hematologia')
  await user.type(screen.getByLabelText('Preço base'), '40.00')
  await user.click(await screen.findByLabelText('Gato'))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() =>
    expect(screen.queryByRole('heading', { name: 'Novo exame' })).not.toBeInTheDocument(),
  )
  expect(await screen.findByRole('heading', { name: 'Urinálise' })).toBeInTheDocument()
})

test('blocks exam creation without at least one species', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(['catalog.read', 'catalog.manage']),
    speciesHandler(),
    categoriesHandler(),
    examsListHandler(),
  )
  renderWithProviders(<ExamsPage />)

  await user.click(await screen.findByRole('button', { name: /Novo exame/i }))
  await user.type(screen.getByLabelText('Código'), 'URI001')
  await user.type(screen.getByLabelText('Nome'), 'Urinálise')
  await user.selectOptions(await screen.findByLabelText('Categoria'), 'Hematologia')
  await user.type(screen.getByLabelText('Preço base'), '40.00')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(
    await screen.findByText('Selecione ao menos uma espécie atendida.'),
  ).toBeInTheDocument()
})
