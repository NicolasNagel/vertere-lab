import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterAll, afterEach, beforeAll, expect, test } from 'vitest'

import { pickOption } from '../../../test/dropdown'
import {
  apiPatient,
  clinicsHandler,
  meHandler,
  speciesHandler,
} from '../../../test/patients-handlers'
import { AuthProvider } from '../../auth/auth-provider'
import { PatientDetailPage } from './patient-detail-page'

const server = setupServer()

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

const READ = ['patients.read']
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

/** Paciente que o "servidor" guarda: o PATCH o altera e o GET devolve a nova versão. */
function statefulPatient(initial: Record<string, unknown> = {}) {
  let current: Record<string, unknown> = apiPatient(initial)
  const patches: Record<string, unknown>[] = []
  const handlers = [
    http.get('/api/v1/patients/p1', () => HttpResponse.json(current)),
    http.patch('/api/v1/patients/p1', async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      patches.push(body)
      current = {
        ...current,
        name: body.name,
        species_id: body.species_id,
        sex: body.sex,
        breed: body.breed,
        age_description: body.age_value ? `${body.age_value} anos` : null,
        owner_name: body.owner_name,
        owner_phone: body.owner_phone,
        notes: body.notes,
        clinic_id: body.clinic_id,
        row_version: (current.row_version as number) + 1,
      }
      return HttpResponse.json(current)
    }),
  ]
  return { handlers, patches, set: (next: Record<string, unknown>) => (current = { ...current, ...next }) }
}

test('shows the patient in blocks with names instead of ids, and a way back to the list', async () => {
  const state = statefulPatient()
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler(), ...state.handlers)
  renderDetail()

  expect(await screen.findByRole('heading', { name: 'Rex', level: 1 })).toBeInTheDocument()
  const identity = within(screen.getByRole('heading', { name: 'Identificação' }).closest('section')!)
  expect(await identity.findByText('Cão')).toBeInTheDocument()
  expect(identity.getByText('SRD')).toBeInTheDocument()
  expect(identity.getByText('Macho')).toBeInTheDocument()
  const owner = within(screen.getByRole('heading', { name: 'Tutor' }).closest('section')!)
  expect(owner.getByText('Maria Souza')).toBeInTheDocument()
  expect(owner.getByText('(47) 99999-0000')).toBeInTheDocument()
  expect(await screen.findAllByText('Clínica Central')).not.toHaveLength(0)
  expect(screen.getByRole('link', { name: /Voltar/ })).toHaveAttribute('href', '/pacientes')
})

test('says not found and says permission apart, and read-only users get no edit buttons', async () => {
  server.use(
    meHandler(READ),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(apiPatient())),
    http.get('/api/v1/patients/missing', () =>
      HttpResponse.json({ error: { code: 'NOT_FOUND', message: 'x' } }, { status: 404 }),
    ),
    http.get('/api/v1/patients/denied', () =>
      HttpResponse.json({ error: { code: 'FORBIDDEN', message: 'x' } }, { status: 403 }),
    ),
  )
  const readOnly = renderDetail('p1')
  await screen.findByRole('heading', { name: 'Rex', level: 1 })
  expect(screen.queryByRole('button', { name: /^Editar/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Inativar paciente/ })).not.toBeInTheDocument()
  readOnly.unmount()

  const missing = renderDetail('missing')
  expect(await screen.findByRole('alert')).toHaveTextContent('Paciente não encontrado.')
  missing.unmount()

  renderDetail('denied')
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Você não tem permissão para ver este paciente.',
  )
})

test('editing the identity block sends the whole patient with the version, no reason, and shows the result', async () => {
  const user = userEvent.setup()
  const state = statefulPatient()
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler(), ...state.handlers)
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar identificação' }))
  const name = screen.getByLabelText('Nome do paciente')
  await user.clear(name)
  await user.type(name, 'Rex Renomeado')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByRole('heading', { name: 'Rex Renomeado', level: 1 })).toBeInTheDocument()
  expect(state.patches).toHaveLength(1)
  expect(state.patches[0]).toMatchObject({
    name: 'Rex Renomeado',
    species_id: 's1',
    sex: 'MALE',
    owner_name: 'Maria Souza',
    clinic_id: 'c1',
    status: 'ACTIVE',
    expected_row_version: 1,
  })
  expect(state.patches[0]).not.toHaveProperty('reason')
  // The block went back to reading mode.
  expect(screen.queryByLabelText('Nome do paciente')).not.toBeInTheDocument()
})

test('owner, species and notes blocks save their own fields without touching the rest', async () => {
  const user = userEvent.setup()
  const state = statefulPatient()
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler(), ...state.handlers)
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar tutor' }))
  const phone = screen.getByLabelText('Telefone do tutor')
  await user.clear(phone)
  await user.type(phone, '(47) 98888-1111')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(state.patches).toHaveLength(1))
  expect(state.patches[0]).toMatchObject({ owner_phone: '(47) 98888-1111', name: 'Rex' })

  await user.click(await screen.findByRole('button', { name: 'Editar observação' }))
  await user.type(screen.getByRole('textbox', { name: 'Observação' }), 'Alérgico a dipirona')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(state.patches).toHaveLength(2))
  expect(state.patches[1]).toMatchObject({
    notes: 'Alérgico a dipirona',
    owner_phone: '(47) 98888-1111',
    expected_row_version: 2,
  })

  await user.click(await screen.findByRole('button', { name: 'Editar identificação' }))
  await pickOption(user, 'Espécie', 'Gato')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(state.patches).toHaveLength(3))
  expect(state.patches[2]).toMatchObject({ species_id: 's2', notes: 'Alérgico a dipirona' })
})

test('moving to another clinic needs a reason, warns that old attendances stay, and sends it', async () => {
  const user = userEvent.setup()
  const state = statefulPatient()
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler(), ...state.handlers)
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar clínica' }))
  // Same clinic: nothing to save, no reason asked.
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  expect(screen.queryByLabelText('Motivo da troca de clínica')).not.toBeInTheDocument()

  await pickOption(user, 'Clínica', 'Clínica Norte')
  expect(screen.getByText(/continuam na clínica em que foram registrados/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()

  await user.type(screen.getByLabelText('Motivo da troca de clínica'), '  Tutor mudou de cidade ')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(state.patches).toHaveLength(1))
  expect(state.patches[0]).toMatchObject({ clinic_id: 'c2', reason: 'Tutor mudou de cidade' })
  expect((await screen.findAllByText('Clínica Norte')).length).toBeGreaterThan(0)
})

test('a legacy patient without a clinic receives one with no reason', async () => {
  const user = userEvent.setup()
  const state = statefulPatient({ clinic_id: null })
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler(), ...state.handlers)
  renderDetail()

  expect((await screen.findAllByText('Sem clínica')).length).toBeGreaterThan(0)
  await user.click(screen.getByRole('button', { name: 'Editar clínica' }))
  await pickOption(user, 'Clínica', 'Clínica Central')
  expect(screen.queryByLabelText('Motivo da troca de clínica')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(state.patches).toHaveLength(1))
  expect(state.patches[0]).toMatchObject({ clinic_id: 'c1' })
  expect(state.patches[0]).not.toHaveProperty('reason')
})

test('the blocks mirror the API limits instead of sending a doomed request', async () => {
  const user = userEvent.setup()
  const state = statefulPatient()
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler(), ...state.handlers)
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar identificação' }))
  await user.click(screen.getByLabelText('Nome do paciente'))
  await user.paste('N'.repeat(201))
  await user.click(screen.getByRole('button', { name: 'Salvar' }))

  expect(await screen.findByText('Use até 200 caracteres.')).toBeInTheDocument()
  expect(state.patches).toHaveLength(0)
})

test('a version conflict shows the message and offers to reload instead of overwriting', async () => {
  const user = userEvent.setup()
  let gets = 0
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () => {
      gets += 1
      return HttpResponse.json(apiPatient({ row_version: gets === 1 ? 1 : 5, name: gets === 1 ? 'Rex' : 'Rex (de outra pessoa)' }))
    }),
    http.patch('/api/v1/patients/p1', () =>
      HttpResponse.json(
        { error: { code: 'CONFLICT', message: 'Este paciente foi alterado por outra pessoa.' } },
        { status: 409 },
      ),
    ),
  )
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar tutor' }))
  await user.type(screen.getByLabelText('Telefone do tutor'), '1')
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('alterado por outra pessoa')

  await user.click(screen.getByRole('button', { name: 'Recarregar paciente' }))
  expect(
    await screen.findByRole('heading', { name: 'Rex (de outra pessoa)', level: 1 }),
  ).toBeInTheDocument()
  // Reloading discards what was typed: the block is back to reading mode, so a later Salvar can
  // never resend that text over what the other person saved without the user having seen it.
  expect(screen.queryByLabelText('Telefone do tutor')).not.toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Editar tutor' }))
  expect(screen.getByLabelText('Telefone do tutor')).toHaveValue('(47) 99999-0000')
})

test('an inactive patient is read-only; Reativar brings the edit buttons back, and a failure is shown', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'INACTIVE'
  let fail = true
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () =>
      HttpResponse.json(apiPatient({ status, row_version: status === 'ACTIVE' ? 3 : 2 })),
    ),
    http.post('/api/v1/patients/p1/reactivate', () => {
      if (fail) {
        return HttpResponse.json(
          { error: { code: 'CONFLICT', message: 'Paciente alterado por outra pessoa.' } },
          { status: 409 },
        )
      }
      status = 'ACTIVE'
      return HttpResponse.json(apiPatient({ status, row_version: 3 }))
    }),
  )
  renderDetail()

  expect(await screen.findByText('Paciente inativo: somente leitura até reativar.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Editar/ })).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Reativar paciente' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Paciente alterado por outra pessoa.')

  fail = false
  await user.click(screen.getByRole('button', { name: 'Reativar paciente' }))
  expect(await screen.findByRole('button', { name: 'Editar identificação' })).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Inativar paciente' })).toBeInTheDocument()
})

test('Inativar paciente keeps the record and turns it read-only', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'ACTIVE'
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () =>
      HttpResponse.json(apiPatient({ status, row_version: status === 'ACTIVE' ? 1 : 2 })),
    ),
    http.post('/api/v1/patients/p1/deactivate', () => {
      status = 'INACTIVE'
      return HttpResponse.json(apiPatient({ status, row_version: 2 }))
    }),
  )
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Inativar paciente' }))
  expect(await screen.findByText('Paciente inativo: somente leitura até reativar.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Editar/ })).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Rex', level: 1 })).toBeInTheDocument()
})

test('a double click on Salvar in a block sends a single PATCH', async () => {
  const user = userEvent.setup()
  let patches = 0
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () => HttpResponse.json(apiPatient())),
    http.patch('/api/v1/patients/p1', async () => {
      patches += 1
      await new Promise((resolve) => setTimeout(resolve, 150))
      return HttpResponse.json(apiPatient({ owner_phone: '(47) 90000-0000', row_version: 2 }))
    }),
  )
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar tutor' }))
  const phone = screen.getByLabelText('Telefone do tutor')
  await user.clear(phone)
  await user.type(phone, '(47) 90000-0000')
  await user.dblClick(screen.getByRole('button', { name: 'Salvar' }))

  await waitFor(() => expect(screen.queryByLabelText('Telefone do tutor')).not.toBeInTheDocument())
  expect(patches).toBe(1)
})

test('a failed load that is not 403 or 404 says it could not load, not that the patient does not exist', async () => {
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () => HttpResponse.json({}, { status: 500 })),
  )
  renderDetail()

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Não foi possível carregar o paciente. Tente novamente.',
  )
})

test('the clinic reason mirrors the 500-character limit without sending the request', async () => {
  const user = userEvent.setup()
  const state = statefulPatient()
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler(), ...state.handlers)
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar clínica' }))
  await pickOption(user, 'Clínica', 'Clínica Norte')
  await user.click(screen.getByLabelText('Motivo da troca de clínica'))
  await user.paste('m'.repeat(501))

  expect(await screen.findByText('Use até 500 caracteres.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  expect(state.patches).toHaveLength(0)
})

test('the clinic dropdown keeps the current clinic even when it is inactive', async () => {
  const user = userEvent.setup()
  const state = statefulPatient({ clinic_id: 'c9' })
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    http.get('/api/v1/clinics', () =>
      HttpResponse.json({
        items: [
          { id: 'c1', name: 'Clínica Central', status: 'ACTIVE' },
          { id: 'c9', name: 'Clínica Desativada', status: 'INACTIVE' },
          { id: 'c8', name: 'Outra Desativada', status: 'INACTIVE' },
        ],
        total: 3,
        page: 1,
        page_size: 100,
      }),
    ),
    ...state.handlers,
  )
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar clínica' }))
  expect(await screen.findByRole('button', { name: /^Clínica Clínica Desativada/ })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /^Clínica Clínica Desativada/ }))
  expect(await screen.findByRole('option', { name: 'Clínica Central' })).toBeInTheDocument()
  expect(screen.queryByRole('option', { name: 'Outra Desativada' })).not.toBeInTheDocument()
})

test('changing only the age enables Salvar, and an untouched block keeps it disabled', async () => {
  const user = userEvent.setup()
  const state = statefulPatient()
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler(), ...state.handlers)
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar identificação' }))
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  await user.type(screen.getByLabelText('Idade'), '4')
  expect(screen.getByRole('button', { name: 'Salvar' })).toBeEnabled()
  await user.click(screen.getByRole('button', { name: 'Salvar' }))
  await waitFor(() => expect(state.patches).toHaveLength(1))
  expect(state.patches[0]).toMatchObject({ age_value: 4, age_unit: 'YEARS' })
})

test('inactivating with a block open returns it to reading mode, and reactivating does not reopen it', async () => {
  const user = userEvent.setup()
  let status: 'ACTIVE' | 'INACTIVE' = 'ACTIVE'
  server.use(
    meHandler(MANAGE),
    speciesHandler(),
    clinicsHandler(),
    http.get('/api/v1/patients/p1', () =>
      HttpResponse.json(apiPatient({ status, row_version: status === 'ACTIVE' ? 1 : 2 })),
    ),
    http.post('/api/v1/patients/p1/deactivate', () => {
      status = 'INACTIVE'
      return HttpResponse.json(apiPatient({ status, row_version: 2 }))
    }),
    http.post('/api/v1/patients/p1/reactivate', () => {
      status = 'ACTIVE'
      return HttpResponse.json(apiPatient({ status, row_version: 3 }))
    }),
  )
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar tutor' }))
  expect(screen.getByLabelText('Nome do tutor')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Inativar paciente' }))
  await screen.findByText('Paciente inativo: somente leitura até reativar.')
  expect(screen.queryByLabelText('Nome do tutor')).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Reativar paciente' }))
  expect(await screen.findByRole('button', { name: 'Editar tutor' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Nome do tutor')).not.toBeInTheDocument()
})

test('keyboard focus follows the editor: first field on open, back to Editar on cancel', async () => {
  const user = userEvent.setup()
  const state = statefulPatient()
  server.use(meHandler(MANAGE), speciesHandler(), clinicsHandler(), ...state.handlers)
  renderDetail()

  await user.click(await screen.findByRole('button', { name: 'Editar tutor' }))
  await waitFor(() => expect(screen.getByLabelText('Nome do tutor')).toHaveFocus())
  await user.click(screen.getByRole('button', { name: 'Cancelar' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Editar tutor' })).toHaveFocus())
})

