import { zodResolver } from '@hookform/resolvers/zod'
import { Controller, useForm } from 'react-hook-form'

import { describeError } from '../../../shared/api/describe-error'
import { Dropdown } from '../../../shared/ui/dropdown'
import { ClinicsIcon, PatientsIcon, UserIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import type { PatientFormValues } from '../api/patients-api'
import { useSpeciesQuery } from '../api/use-species-query'
import { PatientAgeField } from './patient-age-field'
import {
  patientSchema,
  SEX_OPTIONS,
  toApiValues,
  toFormFields,
  type PatientFormFields,
} from './patient-fields'
import '../../attendances/components/attendance-draft-page.css'

interface PatientCreateFormProps {
  formId: string
  submitting: boolean
  error?: unknown
  onSubmitCreate: (values: PatientFormValues) => void
}

/** Cadastro de paciente em seções, no layout do Novo Protocolo. As ações ficam na barra inferior. */
export function PatientCreateForm({
  formId,
  submitting,
  error,
  onSubmitCreate,
}: PatientCreateFormProps) {
  const {
    register,
    control,
    watch,
    setValue,
    handleSubmit,
    formState: { errors },
  } = useForm<PatientFormFields>({
    resolver: zodResolver(patientSchema),
    defaultValues: toFormFields(null),
  })
  const speciesQuery = useSpeciesQuery()
  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const errorMessage = describeError(error)

  return (
    <form
      id={formId}
      noValidate
      onSubmit={handleSubmit((fields) => onSubmitCreate(toApiValues(fields)))}
    >
      <div className="attendance-draft-page__stack">
        <section className="attendance-draft-page__section" aria-labelledby="patient-section-main">
          <h2 id="patient-section-main" className="attendance-draft-page__section-title">
            Paciente
          </h2>
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
                disabled={submitting || clinicsQuery.isLoading}
                errorMessage={errors.clinicId?.message}
              />
            )}
          />
          <div className="attendance-draft-page__row">
            <TextField
              id="patient-name"
              label="Nome do paciente"
              disabled={submitting}
              errorMessage={errors.name?.message}
              {...register('name')}
            />
            <Controller
              control={control}
              name="speciesId"
              render={({ field }) => (
                <Dropdown
                  variant="field"
                  icon={<PatientsIcon />}
                  label="Espécie"
                  placeholder={speciesQuery.isLoading ? 'Carregando…' : 'Selecione a espécie'}
                  options={(speciesQuery.data ?? []).map((species) => ({
                    value: species.id,
                    label: species.name,
                  }))}
                  value={field.value}
                  onChange={field.onChange}
                  disabled={submitting || speciesQuery.isLoading}
                  errorMessage={errors.speciesId?.message}
                />
              )}
            />
          </div>
          <div className="attendance-draft-page__row">
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
            <TextField
              id="patient-breed"
              label="Raça"
              disabled={submitting}
              errorMessage={errors.breed?.message}
              {...register('breed')}
            />
          </div>
          <PatientAgeField
            idPrefix="patient"
            value={watch('ageValue')}
            unit={watch('ageUnit')}
            disabled={submitting}
            errorMessage={errors.ageValue?.message}
            onValueChange={(value) => setValue('ageValue', value, { shouldDirty: true })}
            onUnitChange={(unit) => setValue('ageUnit', unit, { shouldDirty: true })}
          />
        </section>

        <section className="attendance-draft-page__section" aria-labelledby="patient-section-owner">
          <h2 id="patient-section-owner" className="attendance-draft-page__section-title">
            Tutor
          </h2>
          <div className="attendance-draft-page__row">
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
              errorMessage={errors.ownerPhone?.message}
              {...register('ownerPhone')}
            />
          </div>
          <TextField
            id="patient-owner-document"
            label="Documento do tutor"
            disabled={submitting}
            errorMessage={errors.ownerDocument?.message}
            {...register('ownerDocument')}
          />
        </section>

        <section className="attendance-draft-page__section" aria-labelledby="patient-section-notes">
          <h2 id="patient-section-notes" className="attendance-draft-page__section-title">
            Informações adicionais
          </h2>
          <TextField
            id="patient-notes"
            label="Observação"
            disabled={submitting}
            errorMessage={errors.notes?.message}
            {...register('notes')}
          />
        </section>

        {errorMessage && (
          <p role="alert" className="attendance-draft-page__domain-error">
            {errorMessage}
          </p>
        )}
      </div>
    </form>
  )
}
