import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { pickOption } from '../../../test/dropdown'
import { apiPatient, clinicsHandler, meHandler, speciesHandler } from '../../../test/patients-handlers'
import { AuthProvider } from '../../auth/auth-provider'
import { PatientFormPage } from './patient-form-page'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

const MANAGE = ['patients.read', 'patients.manage']

function renderForm() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={['/pacientes/novo']}>
          <Routes>
            <Route path="/pacientes/novo" element={<PatientFormPage />} />
            <Route path="/pacientes/:patientId" element={<p>Página do paciente p2</p>} />
            <Route path="/pacientes" element={<p>Lista de pacientes</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Nome do paciente'), 'Bidu')
  await pickOption(user, 'Clínica', 'Clínica Central')
  await pickOption(user, 'Espécie', 'Gato')
  await user.type(screen.getByLabelText('Nome do tutor'), 'Joana Lima')
}

test('creates a patient with embedded owner data and opens the patient page', async () => {
  const user = userEvent.setup()
  let body: Record<string, unknown> = {}
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.post('/api/v1/patients', async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>
      return HttpResponse.json(apiPatient({ id: 'p2', name: body.name }), { status: 201 })
    }),
  )
  renderForm()

  await fillValidForm(user)
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByText('Página do paciente p2')).toBeInTheDocument()
  expect(body).toMatchObject({
    name: 'Bidu',
    clinic_id: 'c1',
    species_id: 's2',
    owner_name: 'Joana Lima',
  })
})

test('a double click on Salvar creates the patient only once', async () => {
  const user = userEvent.setup()
  let posts = 0
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.post('/api/v1/patients', async () => {
      posts += 1
      await new Promise((resolve) => setTimeout(resolve, 150))
      return HttpResponse.json(apiPatient({ id: 'p2', name: 'Bidu' }), { status: 201 })
    }),
  )
  renderForm()

  await fillValidForm(user)
  await user.dblClick(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByText('Página do paciente p2')).toBeInTheDocument()
  expect(posts).toBe(1)
})

test('the form mirrors the API length limits instead of sending a doomed request', async () => {
  const user = userEvent.setup()
  let posts = 0
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.post('/api/v1/patients', () => {
      posts += 1
      return HttpResponse.json(apiPatient({ id: 'p9' }), { status: 201 })
    }),
  )
  renderForm()

  await user.click(await screen.findByLabelText('Nome do paciente'))
  await user.paste('N'.repeat(201))
  await pickOption(user, 'Clínica', 'Clínica Central')
  await pickOption(user, 'Espécie', 'Gato')
  await user.type(screen.getByLabelText('Nome do tutor'), 'Joana Lima')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByText('Use até 200 caracteres.')).toBeInTheDocument()
  expect(posts).toBe(0)
})

test('Cancelar goes back to the list, and without patients.manage the form is blocked', async () => {
  const user = userEvent.setup()
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler())
  const view = renderForm()

  await user.click(await screen.findByRole('button', { name: 'Cancelar' }))
  expect(await screen.findByText('Lista de pacientes')).toBeInTheDocument()
  view.unmount()
  server.resetHandlers()

  server.use(meHandler(['patients.read']), speciesHandler(), clinicsHandler())
  renderForm()
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Você não tem permissão para cadastrar pacientes.',
  )
  await waitFor(() => expect(screen.queryByLabelText('Nome do paciente')).not.toBeInTheDocument())
})
