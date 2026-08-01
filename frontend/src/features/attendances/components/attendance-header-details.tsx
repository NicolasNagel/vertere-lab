import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { describeError } from '../../../shared/api/describe-error'
import { ApiError } from '../../../shared/api/errors'
import { formatDate } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import { SelectField, type SelectOption } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import { useClinicQuery } from '../../clinics/api/use-clinic-query'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import type { Patient } from '../../patients/api/patients-api'
import { usePatientQuery } from '../../patients/api/use-patient-query'
import { useVeterinarianQuery } from '../../veterinarians/api/use-veterinarian-query'
import { useAllVeterinariansQuery } from '../../veterinarians/api/use-veterinarians-query'
import { attendanceQueryKey } from '../api/use-attendance-query'
import { useUpdateAttendanceMutation } from '../api/use-update-attendance-mutation'
import type { Attendance, CollectionMethod, ServiceLevel } from '../api/attendances-api'
import { PatientPicker } from './patient-picker'
import './attendance-header-details.css'

interface AttendanceHeaderDetailsProps {
  attendance: Attendance
  /** Only `DRAFT` may change clinic/veterinarian/patient/service_date — the
   * backend rejects it otherwise (`AttendanceRecord.update_fields`,
   * `.claude/rules/12-attendance.md`: "CONFIRMED (ainda financeiramente
   * aberto): edição controlada"). The caller decides this, this component
   * just renders read-only vs. editable accordingly. */
  editable: boolean
}

export function AttendanceHeaderDetails({ attendance, editable }: AttendanceHeaderDetailsProps) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [clinicId, setClinicId] = useState('')
  const [veterinarianId, setVeterinarianId] = useState('')
  const [patient, setPatient] = useState<Patient | null>(null)
  const [serviceDate, setServiceDate] = useState('')
  const [collectionMethod, setCollectionMethod] = useState<CollectionMethod>('INTERNAL')
  const [serviceLevel, setServiceLevel] = useState<ServiceLevel>('NORMAL')
  const [notes, setNotes] = useState('')

  const clinicQuery = useClinicQuery(attendance.clinicId)
  const veterinarianQuery = useVeterinarianQuery(attendance.veterinarianId)
  const patientQuery = usePatientQuery(attendance.patientId)

  // The all-pages queries keep the current selection available in large datasets.
  // (unlike the other hooks in this feature) — same as
  // `attendance-draft-form.tsx`, which already fetches both unconditionally
  // for the same reason: these lists are small and TanStack Query caches
  // them, so gating behind `editing` would only add a loading flicker on
  // first "Editar dados" click, not save a real request in practice.
  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const veterinariansQuery = useAllVeterinariansQuery({
    status: 'ACTIVE',
    availableForClinicId: clinicId || undefined,
  })
  const updateMutation = useUpdateAttendanceMutation()

  const errorMessage = describeError(updateMutation.error)
  const isConflict = updateMutation.error instanceof ApiError && updateMutation.error.status === 409

  const clinicOptions: SelectOption[] = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const veterinarianOptions: SelectOption[] = (veterinariansQuery.data?.items ?? []).map((vet) => ({
    value: vet.id,
    label: vet.name,
  }))

  function startEditing() {
    setClinicId(attendance.clinicId)
    setVeterinarianId(attendance.veterinarianId)
    setPatient(patientQuery.data ?? null)
    setServiceDate(attendance.serviceDate ?? '')
    setCollectionMethod(attendance.collectionMethod)
    setServiceLevel(attendance.serviceLevel)
    setNotes(attendance.notes ?? '')
    updateMutation.reset()
    setEditing(true)
  }

  function handleClinicChange(value: string) {
    setClinicId(value)
    setVeterinarianId('')
  }

  const canSave = Boolean(clinicId && veterinarianId && patient) && !updateMutation.isPending

  function handleSave() {
    if (!clinicId || !veterinarianId || !patient) return
    updateMutation.mutate(
      {
        attendanceId: attendance.id,
        rowVersion: attendance.rowVersion,
        input: {
          clinicId,
          veterinarianId,
          patientId: patient.id,
          serviceDate: serviceDate || null,
          collectionMethod,
          serviceLevel,
          notes,
        },
      },
      { onSuccess: () => setEditing(false) },
    )
  }

  function handleReload() {
    void queryClient.invalidateQueries({ queryKey: attendanceQueryKey(attendance.id) })
    setEditing(false)
  }

  return (
    <section className="attendance-header-details">
      <div className="attendance-header-details__header">
        <h2 className="attendance-header-details__title">Dados do atendimento</h2>
        {editable && !editing && (
          <button
            type="button"
            className="attendance-header-details__edit-button"
            onClick={startEditing}
          >
            Editar dados
          </button>
        )}
      </div>

      {!editing && (
        <div className="attendance-header-details__grid">
          <div className="attendance-header-details__field">
            <span className="attendance-header-details__label">Clínica</span>
            <span className="attendance-header-details__value">
              {clinicQuery.data?.name ?? '—'}
            </span>
          </div>
          <div className="attendance-header-details__field">
            <span className="attendance-header-details__label">MÃ©todo de coleta</span>
            <span className="attendance-header-details__value">
              {{
                INTERNAL: 'Internos',
                HELITO_NICOLAS: 'Helito/Nicolas',
                MARLI: 'Marli',
                COURIER: 'Motoboy',
                UBER: 'Uber',
              }[attendance.collectionMethod]}
            </span>
          </div>
          <div className="attendance-header-details__field">
            <span className="attendance-header-details__label">Tipo de atendimento</span>
            <span className="attendance-header-details__value">
              {attendance.serviceLevel === 'ON_CALL' ? 'PlantÃ£o' : 'Normal'}
            </span>
          </div>
          <div className="attendance-header-details__field">
            <span className="attendance-header-details__label">Veterinário</span>
            <span className="attendance-header-details__value">
              {veterinarianQuery.data?.name ?? '—'}
            </span>
          </div>
          <div className="attendance-header-details__field">
            <span className="attendance-header-details__label">Paciente</span>
            <span className="attendance-header-details__value">
              {patientQuery.data
                ? `${patientQuery.data.name} · Tutor: ${patientQuery.data.ownerName}`
                : '—'}
            </span>
          </div>
          <div className="attendance-header-details__field">
            <span className="attendance-header-details__label">Data do atendimento</span>
            <span className="attendance-header-details__value">
              {attendance.serviceDate ? formatDate(attendance.serviceDate) : '—'}
            </span>
          </div>
        </div>
      )}

      {editing && (
        <div className="attendance-header-details__form">
          <div className="attendance-header-details__row">
            <SelectField
              id="attendance-header-clinic"
              label="Clínica solicitante"
              options={[
                { value: '', label: clinicsQuery.isLoading ? 'Carregando…' : 'Selecione a clínica' },
                ...clinicOptions,
              ]}
              disabled={updateMutation.isPending}
              value={clinicId}
              onChange={(event) => handleClinicChange(event.target.value)}
            />
            <SelectField
              id="attendance-header-veterinarian"
              label="Veterinário responsável"
              options={[
                {
                  value: '',
                  label: veterinariansQuery.isLoading ? 'Carregando…' : 'Selecione o veterinário',
                },
                ...veterinarianOptions,
              ]}
              disabled={updateMutation.isPending || !clinicId}
              value={veterinarianId}
              onChange={(event) => setVeterinarianId(event.target.value)}
            />
          </div>

          {/* `canCreate={false}`: criação rápida de paciente durante a edição
              do cabeçalho fica fora desta fatia — troca só entre pacientes
              já cadastrados. Pendência sinalizada, não decisão silenciosa. */}
          <PatientPicker
            selectedPatient={patient}
            disabled={updateMutation.isPending}
            canCreate={false}
            onSelect={setPatient}
            onClear={() => setPatient(null)}
            onRequestCreate={() => undefined}
          />

          <div className="attendance-header-details__row">
            <SelectField
              id="attendance-header-collection-method"
              label="MÃ©todo de coleta"
              value={collectionMethod}
              disabled={updateMutation.isPending}
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
              id="attendance-header-service-level"
              label="Tipo de atendimento"
              value={serviceLevel}
              disabled={updateMutation.isPending}
              options={[
                { value: 'NORMAL', label: 'Normal' },
                { value: 'ON_CALL', label: 'PlantÃ£o' },
              ]}
              onChange={(event) => setServiceLevel(event.target.value as ServiceLevel)}
            />
            <TextField
              id="attendance-header-service-date"
              label="Data do atendimento"
              type="date"
              disabled={updateMutation.isPending}
              value={serviceDate}
              onChange={(event) => setServiceDate(event.target.value)}
            />
            <TextField
              id="attendance-header-notes"
              label="Observações"
              disabled={updateMutation.isPending}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </div>

          {errorMessage && (
            <p className="attendance-header-details__error" role="alert">
              {errorMessage}
            </p>
          )}

          <div className="attendance-header-details__actions">
            <Button type="button" disabled={!canSave} onClick={handleSave}>
              {updateMutation.isPending ? 'Salvando…' : 'Salvar'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={updateMutation.isPending}
              onClick={() => setEditing(false)}
            >
              Cancelar
            </Button>
            {isConflict && (
              <Button type="button" variant="ghost" onClick={handleReload}>
                Recarregar atendimento
              </Button>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
