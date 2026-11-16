import { useState } from 'react'

import { Checkbox } from '../../../shared/ui/checkbox'
import { Dropdown, type DropdownOption } from '../../../shared/ui/dropdown'
import { ClinicsIcon, ExamsIcon, TagIcon, UserIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import type { Patient } from '../../patients/api/patients-api'
import { useAllVeterinariansQuery } from '../../veterinarians/api/use-veterinarians-query'
import {
  COLLECTION_METHOD_LABELS,
  SERVICE_LEVEL_LABELS,
  type Attendance,
  type AttendanceUpdateInput,
  type CollectionMethod,
  type ServiceLevel,
} from '../api/attendances-api'
import { useUpdateAttendanceMutation } from '../api/use-update-attendance-mutation'
import { CorrectionFooter } from './attendance-correction-block'
import { PatientPicker } from './patient-picker'

interface CorrectionFormProps {
  attendance: Attendance
  onClose: () => void
}

/** Salva só os campos que mudaram; o motivo vai junto e fica na auditoria. */
function useHeaderCorrection(attendance: Attendance, onClose: () => void) {
  const [reason, setReason] = useState('')
  const mutation = useUpdateAttendanceMutation()

  function save(input: AttendanceUpdateInput) {
    mutation.mutate(
      {
        attendanceId: attendance.id,
        rowVersion: attendance.rowVersion,
        input: { ...input, reason: reason.trim() },
      },
      { onSuccess: onClose },
    )
  }

  return { reason, setReason, mutation, save }
}

export function RequesterCorrectionForm({ attendance, onClose }: CorrectionFormProps) {
  const [clinicId, setClinicId] = useState(attendance.clinicId)
  const [veterinarianId, setVeterinarianId] = useState(attendance.veterinarianId)
  const { reason, setReason, mutation, save } = useHeaderCorrection(attendance, onClose)

  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const veterinariansQuery = useAllVeterinariansQuery({
    status: 'ACTIVE',
    availableForClinicId: clinicId || undefined,
  })
  const clinicOptions: DropdownOption[] = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const veterinarianOptions: DropdownOption[] = (veterinariansQuery.data?.items ?? []).map((vet) => ({
    value: vet.id,
    label: vet.name,
  }))

  const changed =
    clinicId !== attendance.clinicId || veterinarianId !== attendance.veterinarianId

  return (
    <div className="attendance-correction-block__form">
      <div className="attendance-correction-block__row">
        <Dropdown
          variant="field"
          searchable
          icon={<ClinicsIcon />}
          label="Clínica solicitante"
          placeholder="Selecione a clínica"
          disabled={mutation.isPending}
          value={clinicId}
          options={clinicOptions}
          onChange={(value) => {
            setClinicId(value)
            setVeterinarianId('')
          }}
        />
        <Dropdown
          variant="field"
          searchable
          icon={<UserIcon />}
          label="Veterinário responsável"
          placeholder="Selecione o veterinário"
          disabled={mutation.isPending || !clinicId}
          value={veterinarianId}
          options={veterinarianOptions}
          onChange={setVeterinarianId}
        />
      </div>
      <CorrectionFooter
        attendanceId={attendance.id}
        reason={reason}
        onReasonChange={setReason}
        canSave={changed && Boolean(clinicId) && Boolean(veterinarianId)}
        isPending={mutation.isPending}
        error={mutation.error}
        onSave={() => save({ clinicId, veterinarianId })}
        onCancel={onClose}
      />
    </div>
  )
}

interface PatientCorrectionFormProps extends CorrectionFormProps {
  currentPatient: Patient | undefined
}

export function PatientCorrectionForm({
  attendance,
  currentPatient,
  onClose,
}: PatientCorrectionFormProps) {
  const [patient, setPatient] = useState<Patient | null>(currentPatient ?? null)
  const { reason, setReason, mutation, save } = useHeaderCorrection(attendance, onClose)

  return (
    <div className="attendance-correction-block__form">
      <PatientPicker
        selectedPatient={patient}
        disabled={mutation.isPending}
        canCreate={false}
        onSelect={setPatient}
        onClear={() => setPatient(null)}
        onRequestCreate={() => undefined}
      />
      <CorrectionFooter
        attendanceId={attendance.id}
        reason={reason}
        onReasonChange={setReason}
        canSave={patient !== null && patient.id !== attendance.patientId}
        isPending={mutation.isPending}
        error={mutation.error}
        onSave={() => patient && save({ patientId: patient.id })}
        onCancel={onClose}
      />
    </div>
  )
}

export function ServiceCorrectionForm({ attendance, onClose }: CorrectionFormProps) {
  const [serviceLevel, setServiceLevel] = useState<ServiceLevel>(attendance.serviceLevel)
  const [collectionMethod, setCollectionMethod] = useState<CollectionMethod>(
    attendance.collectionMethod,
  )
  const [serviceDate, setServiceDate] = useState(attendance.serviceDate ?? '')
  const [isUrgent, setIsUrgent] = useState(attendance.isUrgent)
  const { reason, setReason, mutation, save } = useHeaderCorrection(attendance, onClose)

  const input: AttendanceUpdateInput = {}
  if (isUrgent !== attendance.isUrgent) input.isUrgent = isUrgent
  if (serviceLevel !== attendance.serviceLevel) input.serviceLevel = serviceLevel
  if (collectionMethod !== attendance.collectionMethod) input.collectionMethod = collectionMethod
  if (serviceDate && serviceDate !== attendance.serviceDate) input.serviceDate = serviceDate

  return (
    <div className="attendance-correction-block__form">
      <div className="attendance-correction-block__row">
        <Dropdown
          variant="field"
          icon={<TagIcon />}
          label="Tipo de atendimento"
          disabled={mutation.isPending}
          value={serviceLevel}
          options={(Object.keys(SERVICE_LEVEL_LABELS) as ServiceLevel[]).map((level) => ({
            value: level,
            label: SERVICE_LEVEL_LABELS[level],
          }))}
          onChange={(value) => setServiceLevel(value as ServiceLevel)}
        />
        <Dropdown
          variant="field"
          icon={<ExamsIcon />}
          label="Forma de coleta"
          disabled={mutation.isPending}
          value={collectionMethod}
          options={(Object.keys(COLLECTION_METHOD_LABELS) as CollectionMethod[]).map((method) => ({
            value: method,
            label: COLLECTION_METHOD_LABELS[method],
          }))}
          onChange={(value) => setCollectionMethod(value as CollectionMethod)}
        />
        <TextField
          id="correction-service-date"
          label="Data do atendimento"
          type="date"
          disabled={mutation.isPending}
          value={serviceDate}
          onChange={(event) => setServiceDate(event.target.value)}
        />
      </div>
      <Checkbox
        id="correction-urgent"
        label="Atendimento urgente"
        checked={isUrgent}
        disabled={mutation.isPending}
        onChange={(event) => setIsUrgent(event.target.checked)}
      />
      <CorrectionFooter
        attendanceId={attendance.id}
        reason={reason}
        onReasonChange={setReason}
        canSave={Object.keys(input).length > 0}
        isPending={mutation.isPending}
        error={mutation.error}
        onSave={() => save(input)}
        onCancel={onClose}
      />
    </div>
  )
}

export function NotesCorrectionForm({ attendance, onClose }: CorrectionFormProps) {
  const [notes, setNotes] = useState(attendance.notes ?? '')
  const { reason, setReason, mutation, save } = useHeaderCorrection(attendance, onClose)

  return (
    <div className="attendance-correction-block__form">
      <TextField
        id="correction-notes"
        label="Observações"
        disabled={mutation.isPending}
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
      />
      <CorrectionFooter
        attendanceId={attendance.id}
        reason={reason}
        onReasonChange={setReason}
        canSave={notes !== (attendance.notes ?? '')}
        isPending={mutation.isPending}
        error={mutation.error}
        onSave={() => save({ notes })}
        onCancel={onClose}
      />
    </div>
  )
}
