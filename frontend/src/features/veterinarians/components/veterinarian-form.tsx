import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { Button } from '../../../shared/ui/button'
import { Checkbox } from '../../../shared/ui/checkbox'
import { SelectField } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import { ApiError } from '../../../shared/api/errors'
import type {
  Veterinarian,
  VeterinarianFormValues,
  VeterinarianStatus,
} from '../api/veterinarians-api'
import './veterinarian-form.css'

const veterinarianSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome do veterinário.'),
  crmv: z.string().trim().min(1, 'Informe o CRMV.'),
  phone: z.string().trim(),
  email: z.string().trim(),
  isAutonomous: z.boolean(),
  status: z.enum(['ACTIVE', 'INACTIVE']),
  notes: z.string().trim(),
})

type VeterinarianFormFields = z.infer<typeof veterinarianSchema>

const STATUS_OPTIONS: { value: VeterinarianStatus; label: string }[] = [
  { value: 'ACTIVE', label: 'Ativo' },
  { value: 'INACTIVE', label: 'Inativo' },
]

function toFormFields(veterinarian: Veterinarian | null): VeterinarianFormFields {
  return {
    name: veterinarian?.name ?? '',
    crmv: veterinarian?.crmv ?? '',
    phone: veterinarian?.phone ?? '',
    email: veterinarian?.email ?? '',
    isAutonomous: veterinarian?.isAutonomous ?? false,
    status: veterinarian?.status ?? 'ACTIVE',
    notes: veterinarian?.notes ?? '',
  }
}

function toApiValues(fields: VeterinarianFormFields): VeterinarianFormValues {
  return {
    name: fields.name,
    crmv: fields.crmv,
    phone: fields.phone || null,
    email: fields.email || null,
    isAutonomous: fields.isAutonomous,
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

interface VeterinarianFormProps {
  veterinarian: Veterinarian | null
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmitCreate?: (values: VeterinarianFormValues, clinicIds: string[]) => void
  onSubmitUpdate?: (values: VeterinarianFormValues & { status: VeterinarianStatus }) => void
}

export function VeterinarianForm({
  veterinarian,
  submitting,
  error,
  onCancel,
  onSubmitCreate,
  onSubmitUpdate,
}: VeterinarianFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<VeterinarianFormFields>({
    resolver: zodResolver(veterinarianSchema),
    defaultValues: toFormFields(veterinarian),
  })

  const isAutonomous = watch('isAutonomous')
  const [selectedClinicIds, setSelectedClinicIds] = useState<string[]>([])
  const [clinicsError, setClinicsError] = useState<string | null>(null)
  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const activeClinics = clinicsQuery.data?.items ?? []

  function toggleClinic(clinicId: string) {
    setSelectedClinicIds((current) =>
      current.includes(clinicId)
        ? current.filter((id) => id !== clinicId)
        : [...current, clinicId],
    )
  }

  const onSubmit = handleSubmit((fields) => {
    if (veterinarian) {
      onSubmitUpdate?.({ ...toApiValues(fields), status: fields.status })
      return
    }
    if (!fields.isAutonomous && selectedClinicIds.length === 0) {
      setClinicsError('Selecione ao menos uma clínica ou marque como autônomo.')
      return
    }
    setClinicsError(null)
    onSubmitCreate?.(toApiValues(fields), selectedClinicIds)
  })

  const errorMessage = describeError(error)

  return (
    <form className="veterinarian-form" onSubmit={onSubmit} noValidate>
      <TextField
        id="veterinarian-name"
        label="Nome"
        disabled={submitting}
        errorMessage={errors.name?.message}
        {...register('name')}
      />

      <div className="veterinarian-form__row">
        <TextField
          id="veterinarian-crmv"
          label="CRMV"
          disabled={submitting}
          errorMessage={errors.crmv?.message}
          {...register('crmv')}
        />
        {veterinarian && (
          <SelectField
            id="veterinarian-status"
            label="Status"
            options={STATUS_OPTIONS}
            disabled={submitting}
            {...register('status')}
          />
        )}
      </div>

      <div className="veterinarian-form__row">
        <TextField
          id="veterinarian-phone"
          label="Telefone"
          disabled={submitting}
          {...register('phone')}
        />
        <TextField
          id="veterinarian-email"
          label="E-mail"
          disabled={submitting}
          {...register('email')}
        />
      </div>

      <Checkbox
        className="veterinarian-form__autonomous"
        label="Veterinário autônomo"
        disabled={submitting}
        {...register('isAutonomous')}
      />

      {!veterinarian && (
        <>
          <p className="veterinarian-form__section-title">Clínica(s) vinculada(s)</p>
          <p className="veterinarian-form__clinics-hint">
            {isAutonomous
              ? 'Opcional para veterinário autônomo.'
              : 'Obrigatório para veterinário não autônomo.'}
          </p>
          {clinicsQuery.isLoading && (
            <p className="veterinarian-form__clinics-hint">Carregando clínicas…</p>
          )}
          {!clinicsQuery.isLoading && activeClinics.length > 0 && (
            <div className="veterinarian-form__clinics-list" role="group" aria-label="Clínicas">
              {activeClinics.map((clinic) => (
                <Checkbox
                  key={clinic.id}
                  label={clinic.name}
                  disabled={submitting}
                  checked={selectedClinicIds.includes(clinic.id)}
                  onChange={() => toggleClinic(clinic.id)}
                />
              ))}
            </div>
          )}
          {clinicsError && (
            <p role="alert" className="veterinarian-form__domain-error">
              {clinicsError}
            </p>
          )}
        </>
      )}

      <TextField
        id="veterinarian-notes"
        label="Observação"
        disabled={submitting}
        {...register('notes')}
      />

      {errorMessage && (
        <p role="alert" className="veterinarian-form__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="veterinarian-form__actions">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" className="veterinarian-form__submit" disabled={submitting}>
          {submitting ? 'Salvando…' : 'Salvar'}
        </Button>
      </div>
    </form>
  )
}
