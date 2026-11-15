import { zodResolver } from '@hookform/resolvers/zod'
import { Controller, useForm } from 'react-hook-form'
import { z } from 'zod'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'
import { Dropdown } from '../../../shared/ui/dropdown'
import { TextField } from '../../../shared/ui/text-field'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import type { PatientFormValues, PatientSex } from '../../patients/api/patients-api'
import { PatientAgeField } from '../../patients/components/patient-age-field'
import {
  ageFieldsShape,
  ageToApi,
  validateAge,
} from '../../patients/components/patient-age-schema'
import './attendance-patient-form.css'

const attendancePatientSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome do paciente.'),
  speciesId: z.string().trim().min(1, 'Selecione a espécie.'),
  sex: z.enum(['MALE', 'FEMALE']),
  breed: z.string().trim(),
  ...ageFieldsShape,
  ownerName: z.string().trim().min(1, 'Informe o nome do tutor.'),
}).superRefine(validateAge)

type AttendancePatientFields = z.infer<typeof attendancePatientSchema>

function toApiValues(fields: AttendancePatientFields, clinicId: string): PatientFormValues {
  return {
    clinicId,
    name: fields.name,
    speciesId: fields.speciesId,
    sex: fields.sex,
    breed: fields.breed || null,
    ...ageToApi(fields),
    ownerName: fields.ownerName,
    ownerPhone: null,
    ownerDocument: null,
    notes: null,
  }
}

function describeError(error: unknown): string | null {
  if (error === null || error === undefined) return null
  if (error instanceof ApiError) return error.message
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}

interface AttendancePatientFormProps {
  clinicId: string
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmitCreate: (values: PatientFormValues) => void
}

/** Cadastro rápido de paciente durante a abertura de atendimento — campos e
 * layout batem com a Tela 4 do mockup (3 colunas, Sexo como alternância em
 * vez de dropdown), por isso é um formulário próprio em vez de reaproveitar
 * `PatientForm` (que serve o cadastro completo em Pacientes, com
 * telefone/documento/observação e layout de 2 colunas — divergiu demais
 * para forçar o mesmo componente sem quebrar um dos dois lugares). */
export function AttendancePatientForm({
  clinicId,
  submitting,
  error,
  onCancel,
  onSubmitCreate,
}: AttendancePatientFormProps) {
  const {
    register,
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<AttendancePatientFields>({
    resolver: zodResolver(attendancePatientSchema),
    defaultValues: {
      name: '',
      speciesId: '',
      sex: 'MALE',
      breed: '',
      ageValue: '',
      ageUnit: 'YEARS',
      ownerName: '',
    },
  })

  const speciesQuery = useSpeciesQuery()
  const speciesOptions = speciesQuery.data ?? []
  const sex = watch('sex')
  const speciesId = watch('speciesId')

  const onSubmit = handleSubmit((fields) => {
    onSubmitCreate(toApiValues(fields, clinicId))
  })

  function selectSex(value: PatientSex) {
    setValue('sex', value)
  }

  const errorMessage = describeError(error)

  return (
    <form className="attendance-patient-form" onSubmit={onSubmit} noValidate>
      <div className="attendance-patient-form__row attendance-patient-form__row--pair">
        <TextField
          id="attendance-patient-name"
          label="Nome do paciente"
          disabled={submitting}
          errorMessage={errors.name?.message}
          {...register('name')}
        />
        <TextField
          id="attendance-patient-owner-name"
          label="Tutor / Proprietário"
          disabled={submitting}
          errorMessage={errors.ownerName?.message}
          {...register('ownerName')}
        />
      </div>

      <div className="attendance-patient-form__row attendance-patient-form__row--details">
        <Dropdown
          variant="field"
          label="Espécie"
          placeholder={speciesQuery.isLoading ? 'Carregando…' : 'Selecione…'}
          options={speciesOptions.map((species) => ({ value: species.id, label: species.name }))}
          disabled={submitting || speciesQuery.isLoading}
          value={speciesId}
          errorMessage={errors.speciesId?.message}
          onChange={(value) => setValue('speciesId', value, { shouldValidate: true })}
        />
        <TextField
          id="attendance-patient-breed"
          label="Raça"
          disabled={submitting}
          {...register('breed')}
        />
        <Controller
          control={control}
          name="ageValue"
          render={({ field: valueField }) => (
            <Controller
              control={control}
              name="ageUnit"
              render={({ field: unitField }) => (
                <PatientAgeField
                  idPrefix="attendance-patient"
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
        <div className="attendance-patient-form__field">
          <span className="attendance-patient-form__label">Sexo</span>
          <div className="attendance-patient-form__toggle-group" role="group" aria-label="Sexo">
            <button
              type="button"
              className="attendance-patient-form__toggle"
              data-active={sex === 'MALE'}
              aria-pressed={sex === 'MALE'}
              disabled={submitting}
              onClick={() => selectSex('MALE')}
            >
              Macho
            </button>
            <button
              type="button"
              className="attendance-patient-form__toggle"
              data-active={sex === 'FEMALE'}
              aria-pressed={sex === 'FEMALE'}
              disabled={submitting}
              onClick={() => selectSex('FEMALE')}
            >
              Fêmea
            </button>
          </div>
        </div>
      </div>

      {errorMessage && (
        <p role="alert" className="attendance-patient-form__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="attendance-patient-form__actions">
        <Button type="button" variant="cancel" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Salvando…' : 'Salvar'}
        </Button>
      </div>
    </form>
  )
}
