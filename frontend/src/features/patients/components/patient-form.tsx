import { zodResolver } from '@hookform/resolvers/zod'
import { Controller, useForm } from 'react-hook-form'

import { Button } from '../../../shared/ui/button'
import { Dropdown } from '../../../shared/ui/dropdown'
import { ClinicsIcon, PatientsIcon, TagIcon, UserIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import { ApiError } from '../../../shared/api/errors'
import { useSpeciesQuery } from '../api/use-species-query'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import type { Patient, PatientFormValues, PatientStatus } from '../api/patients-api'
import { PatientAgeField } from './patient-age-field'
import {
  patientSchema,
  SEX_OPTIONS,
  toApiValues,
  toFormFields,
  type PatientFormFields,
} from './patient-fields'
import './patient-form.css'

const STATUS_OPTIONS: { value: PatientStatus; label: string }[] = [
  { value: 'ACTIVE', label: 'Ativo' },
  { value: 'INACTIVE', label: 'Inativo' },
]

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
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<PatientFormFields>({
    resolver: zodResolver(patientSchema),
    defaultValues: toFormFields(patient),
  })

  const speciesQuery = useSpeciesQuery()
  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
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
      <Controller
        control={control}
        name="clinicId"
        render={({ field }) => (
          <Dropdown
            variant="field"
            searchable
            icon={<ClinicsIcon />}
            label="Clínica"
            placeholder={clinicsQuery.isLoading ? 'Carregando…' : 'Selecione a clínica'}
            options={(clinicsQuery.data?.items ?? []).map((clinic) => ({
              value: clinic.id,
              label: clinic.name,
            }))}
            value={field.value}
            onChange={field.onChange}
            // Changing a patient's clinic needs a reason (the API rejects it otherwise); until the
            // detail screen offers that, an existing patient keeps its clinic here.
            disabled={submitting || clinicsQuery.isLoading || patient !== null}
            errorMessage={errors.clinicId?.message}
          />
        )}
      />
      <div className="patient-form__row">
        <TextField
          id="patient-name"
          label="Nome do paciente"
          disabled={submitting}
          errorMessage={errors.name?.message}
          {...register('name')}
        />
        {patient && (
          <Controller
            control={control}
            name="status"
            render={({ field }) => (
              <Dropdown
                variant="field"
                icon={<TagIcon />}
                label="Status"
                options={STATUS_OPTIONS}
                value={field.value}
                onChange={field.onChange}
                disabled={submitting}
              />
            )}
          />
        )}
      </div>

      <div className="patient-form__row">
        <Controller
          control={control}
          name="speciesId"
          render={({ field }) => (
            <Dropdown
              variant="field"
              icon={<PatientsIcon />}
              label="Espécie"
              placeholder={speciesQuery.isLoading ? 'Carregando…' : 'Selecione a espécie'}
              options={speciesOptions.map((species) => ({ value: species.id, label: species.name }))}
              value={field.value}
              onChange={field.onChange}
              disabled={submitting || speciesQuery.isLoading}
              errorMessage={errors.speciesId?.message}
            />
          )}
        />
        <Controller
          control={control}
          name="sex"
          render={({ field }) => (
            <Dropdown
              variant="field"
              icon={<UserIcon />}
              label="Sexo"
              options={SEX_OPTIONS}
              value={field.value}
              onChange={field.onChange}
              disabled={submitting}
            />
          )}
        />
      </div>

      <div className="patient-form__row">
        <TextField id="patient-breed" label="Raça" disabled={submitting} {...register('breed')} />
        <Controller
          control={control}
          name="ageValue"
          render={({ field: valueField }) => (
            <Controller
              control={control}
              name="ageUnit"
              render={({ field: unitField }) => (
                <PatientAgeField
                  idPrefix="patient"
                  value={valueField.value}
                  unit={unitField.value}
                  disabled={submitting}
                  errorMessage={errors.ageValue?.message}
                  onValueChange={valueField.onChange}
                  onUnitChange={unitField.onChange}
                />
              )}
            />
          )}
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
        <Button type="button" variant="cancel" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" className="patient-form__submit" disabled={submitting}>
          {submitting ? 'Salvando…' : 'Salvar'}
        </Button>
      </div>
    </form>
  )
}
