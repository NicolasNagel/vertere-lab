import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '../../../shared/ui/button'
import { SelectField } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import { ApiError } from '../../../shared/api/errors'
import { useSpeciesQuery } from '../api/use-species-query'
import type { Patient, PatientFormValues, PatientStatus } from '../api/patients-api'
import './patient-form.css'

const patientSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome do paciente.'),
  speciesId: z.string().trim().min(1, 'Selecione a espécie.'),
  sex: z.enum(['MALE', 'FEMALE']),
  breed: z.string().trim(),
  ageDescription: z.string().trim(),
  ownerName: z.string().trim().min(1, 'Informe o nome do tutor.'),
  ownerPhone: z.string().trim(),
  ownerDocument: z.string().trim(),
  status: z.enum(['ACTIVE', 'INACTIVE']),
  notes: z.string().trim(),
})

type PatientFormFields = z.infer<typeof patientSchema>

const SEX_OPTIONS: { value: 'MALE' | 'FEMALE'; label: string }[] = [
  { value: 'MALE', label: 'Macho' },
  { value: 'FEMALE', label: 'Fêmea' },
]

const STATUS_OPTIONS: { value: PatientStatus; label: string }[] = [
  { value: 'ACTIVE', label: 'Ativo' },
  { value: 'INACTIVE', label: 'Inativo' },
]

function toFormFields(patient: Patient | null): PatientFormFields {
  return {
    name: patient?.name ?? '',
    speciesId: patient?.speciesId ?? '',
    sex: patient?.sex ?? 'MALE',
    breed: patient?.breed ?? '',
    ageDescription: patient?.ageDescription ?? '',
    ownerName: patient?.ownerName ?? '',
    ownerPhone: patient?.ownerPhone ?? '',
    ownerDocument: patient?.ownerDocument ?? '',
    status: patient?.status ?? 'ACTIVE',
    notes: patient?.notes ?? '',
  }
}

function toApiValues(fields: PatientFormFields): PatientFormValues {
  return {
    name: fields.name,
    speciesId: fields.speciesId,
    sex: fields.sex,
    breed: fields.breed || null,
    ageDescription: fields.ageDescription || null,
    ownerName: fields.ownerName,
    ownerPhone: fields.ownerPhone || null,
    ownerDocument: fields.ownerDocument || null,
    notes: fields.notes || null,
  }
}

function describeError(error: unknown): string | null {
  if (error === null || error === undefined) {
    return null
  }
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}

interface PatientFormProps {
  patient: Patient | null
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmitCreate?: (values: PatientFormValues) => void
  onSubmitUpdate?: (values: PatientFormValues & { status: PatientStatus }) => void
}

export function PatientForm({
  patient,
  submitting,
  error,
  onCancel,
  onSubmitCreate,
  onSubmitUpdate,
}: PatientFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<PatientFormFields>({
    resolver: zodResolver(patientSchema),
    defaultValues: toFormFields(patient),
  })

  const speciesQuery = useSpeciesQuery()
  const speciesOptions = speciesQuery.data ?? []

  const onSubmit = handleSubmit((fields) => {
    if (patient) {
      onSubmitUpdate?.({ ...toApiValues(fields), status: fields.status })
      return
    }
    onSubmitCreate?.(toApiValues(fields))
  })

  const errorMessage = describeError(error)

  return (
    <form className="patient-form" onSubmit={onSubmit} noValidate>
      <div className="patient-form__row">
        <TextField
          id="patient-name"
          label="Nome do paciente"
          disabled={submitting}
          errorMessage={errors.name?.message}
          {...register('name')}
        />
        {patient && (
          <SelectField
            id="patient-status"
            label="Status"
            options={STATUS_OPTIONS}
            disabled={submitting}
            {...register('status')}
          />
        )}
      </div>

      <div className="patient-form__row">
        <SelectField
          id="patient-species"
          label="Espécie"
          options={[
            { value: '', label: speciesQuery.isLoading ? 'Carregando…' : 'Selecione…' },
            ...speciesOptions.map((species) => ({ value: species.id, label: species.name })),
          ]}
          disabled={submitting || speciesQuery.isLoading}
          errorMessage={errors.speciesId?.message}
          {...register('speciesId')}
        />
        <SelectField
          id="patient-sex"
          label="Sexo"
          options={SEX_OPTIONS}
          disabled={submitting}
          {...register('sex')}
        />
      </div>

      <div className="patient-form__row">
        <TextField id="patient-breed" label="Raça" disabled={submitting} {...register('breed')} />
        <TextField
          id="patient-age"
          label="Idade"
          disabled={submitting}
          {...register('ageDescription')}
        />
      </div>

      <p className="patient-form__section-title">Tutor</p>
      <div className="patient-form__row">
        <TextField
          id="patient-owner-name"
          label="Nome do tutor"
          disabled={submitting}
          errorMessage={errors.ownerName?.message}
          {...register('ownerName')}
        />
        <TextField
          id="patient-owner-phone"
          label="Telefone do tutor"
          disabled={submitting}
          {...register('ownerPhone')}
        />
      </div>
      <TextField
        id="patient-owner-document"
        label="Documento do tutor"
        disabled={submitting}
        {...register('ownerDocument')}
      />
      <TextField id="patient-notes" label="Observação" disabled={submitting} {...register('notes')} />

      {errorMessage && (
        <p role="alert" className="patient-form__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="patient-form__actions">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" className="patient-form__submit" disabled={submitting}>
          {submitting ? 'Salvando…' : 'Salvar'}
        </Button>
      </div>
    </form>
  )
}
