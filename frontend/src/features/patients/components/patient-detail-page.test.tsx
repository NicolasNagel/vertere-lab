import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { apiPatient, clinicsHandler, meHandler, speciesHandler } from '../../../test/patients-handlers'
import { AuthProvider } from '../../auth/auth-provider'
import { PatientDetailPage } from './patient-detail-page'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

const MANAGE = ['patients.read', 'patients.manage']

function renderDetail(id = 'p1') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[`/pacientes/${id}`]}>
          <Routes>
            <Route path="/pacientes/:patientId" element={<PatientDetailPage />} />
            <Route path="/pacientes" element={<p>Lista de pacientes</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

test('shows the patient, links back to the list and says when the patient does not exist', async () => {
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(apiPatient())),
    http.get('/api/v1/patients/missing', () =>
      HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'x' } }, { status: 404 }),
    ),
  )
  const view = renderDetail('p1')
  expect(await screen.findByRole('heading', { name: 'Rex' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Voltar para pacientes' })).toHaveAttribute(
    'href',
    '/pacientes',
  )
  view.unmount()

  renderDetail('missing')
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Paciente não encontrado.',
  )
})

test('an inactive patient offers Reativar instead of Editar, and reactivating brings Editar back', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'INACTIVE'
  const patientBody = () => apiPatient({ status, row_version: status === 'ACTIVE' ? 3 : 2 })
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(patientBody())),
    http.post('/api/v1/patients/p1/reactivate', () => {
      status = 'ACTIVE'
      return HttpResponse.json(patientBody())
    }),
  )
  renderDetail()

  expect(await screen.findByRole('button', { name: 'Reativar' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Reativar' }))
  expect(await screen.findByRole('button', { name: 'Editar' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Reativar' })).not.toBeInTheDocument()
})

test('deactivates from the menu and keeps the record', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'ACTIVE'
  const patientBody = () => apiPatient({ status, row_version: status === 'ACTIVE' ? 1 : 2 })
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(patientBody())),
    http.post('/api/v1/patients/p1/deactivate', () => {
      status = 'INACTIVE'
      return HttpResponse.json(patientBody())
    }),
  )
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Mais ações' }))
  await user.click(await screen.findByRole('menuitem', { name: 'Inativar' }))
  expect(await screen.findByText('Inativo')).toBeInTheDocument()
})

test('editing an existing patient does not let the clinic change (that needs a reason)', async () => {
  const user = userEvent.setup()
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(apiPatient({ clinic_id: 'c1' }))),
  )
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar' }))
  expect(await screen.findByLabelText('Nome do paciente')).toBeEnabled()
  expect(screen.getByRole('button', { name: /Clínica/ })).toBeDisabled()
})
