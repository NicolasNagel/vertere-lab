import { useState, type FormEvent } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { SelectField, type SelectOption } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import { useAuth } from '../../auth/auth-context'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import type { Patient } from '../../patients/api/patients-api'
import { useAllVeterinariansQuery } from '../../veterinarians/api/use-veterinarians-query'
import { useCreateAttendanceDraftMutation } from '../api/use-create-attendance-draft-mutation'
import type { Attendance, CollectionMethod, ServiceLevel } from '../api/attendances-api'
import { CreatePatientModal } from './create-patient-modal'
import { PatientPicker } from './patient-picker'
import './attendance-draft-form.css'

function describeError(error: unknown): string | null {
  if (error === null || error === undefined) return null
  if (error instanceof ApiError) return error.message
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}

interface AttendanceDraftFormProps {
  onCreated: (attendance: Attendance) => void
  onCancel: () => void
}

export function AttendanceDraftForm({ onCreated, onCancel }: AttendanceDraftFormProps) {
  const { user } = useAuth()
  const canCreatePatient = user?.permissions.includes('patients.manage') ?? false

  const [clinicId, setClinicId] = useState('')
  const [veterinarianId, setVeterinarianId] = useState('')
  const [patient, setPatient] = useState<Patient | null>(null)
  const [serviceDate, setServiceDate] = useState('')
  const [collectionMethod, setCollectionMethod] = useState<CollectionMethod>('INTERNAL')
  const [serviceLevel, setServiceLevel] = useState<ServiceLevel>('NORMAL')
  const [notes, setNotes] = useState('')
  const [creatingPatientWithName, setCreatingPatientWithName] = useState<string | null>(null)

  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  // Autônomo aparece pra qualquer clínica; vinculado só aparece pra quem
  // ele está de fato vinculado — mesma regra que o backend revalida em
  // /confirm (`.claude/rules/12-attendance.md`). Filtrado no servidor: a
  // listagem de veterinários não carrega os vínculos de clínica por item
  // (só o endpoint de detalhe carrega), então isso não dá pra fazer no
  // cliente.
  const veterinariansQuery = useAllVeterinariansQuery({
    status: 'ACTIVE',
    availableForClinicId: clinicId || undefined,
  })
  const createDraftMutation = useCreateAttendanceDraftMutation()

  const clinicOptions: SelectOption[] = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))

  const veterinarianOptions: SelectOption[] = (veterinariansQuery.data?.items ?? []).map(
    (veterinarian) => ({ value: veterinarian.id, label: veterinarian.name }),
  )

  const canSubmit = Boolean(clinicId && veterinarianId && patient) && !createDraftMutation.isPending
  const errorMessage = describeError(createDraftMutation.error)

  function handleClinicChange(value: string) {
    setClinicId(value)
    // A lista de veterinários elegíveis é buscada de novo no servidor ao
    // trocar de clínica (não dá pra saber de forma síncrona se a seleção
    // atual continua válida) — mais simples e sempre correto é limpar e
    // deixar o usuário escolher de novo, em vez de arriscar manter uma
    // seleção que não pertence à clínica nova.
    setVeterinarianId('')
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!clinicId || !veterinarianId || !patient) return
    createDraftMutation.mutate(
      {
        clinicId,
        veterinarianId,
        patientId: patient.id,
        serviceDate: serviceDate || null,
        collectionMethod,
        serviceLevel,
        notes: notes.trim() || null,
      },
      { onSuccess: onCreated },
    )
  }

  return (
    <>
      <form className="attendance-draft-form" onSubmit={handleSubmit} noValidate>
        <section className="attendance-draft-form__section">
          <h2 className="attendance-draft-form__section-title">Solicitante</h2>
          <div className="attendance-draft-form__row">
            <SelectField
              id="attendance-draft-clinic"
              label="Clínica solicitante"
              options={[
                {
                  value: '',
                  label: clinicsQuery.isLoading ? 'Carregando…' : 'Selecione a clínica',
                },
                ...clinicOptions,
              ]}
              disabled={createDraftMutation.isPending}
              value={clinicId}
              onChange={(event) => handleClinicChange(event.target.value)}
            />
            {clinicsQuery.isError && (
              <p role="alert" className="attendance-draft-form__domain-error">
                Não foi possível carregar as clínicas.
              </p>
            )}
            <SelectField
              id="attendance-draft-veterinarian"
              label="Veterinário responsável"
              options={[
                {
                  value: '',
                  label: veterinariansQuery.isLoading ? 'Carregando…' : 'Selecione o veterinário',
                },
                ...veterinarianOptions,
              ]}
              disabled={createDraftMutation.isPending || !clinicId}
              value={veterinarianId}
              onChange={(event) => setVeterinarianId(event.target.value)}
            />
            {clinicId && veterinariansQuery.isError && (
              <p role="alert" className="attendance-draft-form__domain-error">
                Não foi possível carregar os veterinários.
              </p>
            )}
          </div>
        </section>

        <section className="attendance-draft-form__section">
          <h2 className="attendance-draft-form__section-title">Paciente</h2>
          <PatientPicker
            selectedPatient={patient}
            disabled={createDraftMutation.isPending}
            canCreate={canCreatePatient}
            onSelect={setPatient}
            onClear={() => setPatient(null)}
            onRequestCreate={(searchTerm) => setCreatingPatientWithName(searchTerm)}
          />
        </section>

        <section className="attendance-draft-form__section">
          <h2 className="attendance-draft-form__section-title">Atendimento</h2>
          <div className="attendance-draft-form__row">
            <SelectField
              id="attendance-draft-collection-method"
              label="MÃ©todo de coleta"
              value={collectionMethod}
              disabled={createDraftMutation.isPending}
              options={[
                { value: 'INTERNAL', label: 'Internos' },
                { value: 'HELITO_NICOLAS', label: 'Helito/Nicolas' },
                { value: 'MARLI', label: 'Marli' },
                { value: 'COURIER', label: 'Motoboy' },
                { value: 'UBER', label: 'Uber' },
              ]}
              onChange={(event) => setCollectionMethod(event.target.value as CollectionMethod)}
            />
            <SelectField
              id="attendance-draft-service-level"
              label="Tipo de atendimento"
              value={serviceLevel}
              disabled={createDraftMutation.isPending}
              options={[
                { value: 'NORMAL', label: 'Normal' },
                { value: 'ON_CALL', label: 'PlantÃ£o' },
              ]}
              onChange={(event) => setServiceLevel(event.target.value as ServiceLevel)}
            />
            <TextField
              id="attendance-draft-service-date"
              label="Data do atendimento"
              type="date"
              disabled={createDraftMutation.isPending}
              value={serviceDate}
              onChange={(event) => setServiceDate(event.target.value)}
            />
          </div>
          <TextField
            id="attendance-draft-notes"
            label="Observações"
            disabled={createDraftMutation.isPending}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </section>

        {errorMessage && (
          <p role="alert" className="attendance-draft-form__domain-error">
            {errorMessage}
          </p>
        )}

        <div className="attendance-draft-form__actions">
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            disabled={createDraftMutation.isPending}
          >
            Cancelar
          </Button>
          <Button type="submit" disabled={!canSubmit}>
            {createDraftMutation.isPending ? 'Criando…' : 'Criar rascunho'}
          </Button>
        </div>
      </form>

      {creatingPatientWithName !== null && (
        <CreatePatientModal
          initialName={creatingPatientWithName}
          onClose={() => setCreatingPatientWithName(null)}
          onCreated={(createdPatient) => {
            setPatient(createdPatient)
            setCreatingPatientWithName(null)
          }}
        />
      )}
    </>
  )
}
