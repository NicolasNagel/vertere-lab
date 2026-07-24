import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { Button } from '../../../shared/ui/button'
import { SelectField } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import { ApiError } from '../../../shared/api/errors'
import { formatTaxId } from '../../../shared/lib/formatters'
import type { Clinic, ClinicFormValues, ClinicStatus } from '../api/clinics-api'
import './clinic-form.css'

const clinicSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome da clínica.'),
  taxId: z.string().trim(),
  phone: z.string().trim(),
  email: z.string().trim(),
  status: z.enum(['ACTIVE', 'INACTIVE', 'DELINQUENT', 'SPECIAL']),
  addressZipCode: z.string().trim(),
  addressStreet: z.string().trim(),
  addressNumber: z.string().trim(),
  addressNeighborhood: z.string().trim(),
  addressCity: z.string().trim(),
  addressState: z.string().trim(),
  addressComplement: z.string().trim(),
  notes: z.string().trim(),
})

type ClinicFormFields = z.infer<typeof clinicSchema>

const STATUS_OPTIONS: { value: ClinicStatus; label: string }[] = [
  { value: 'ACTIVE', label: 'Ativo' },
  { value: 'INACTIVE', label: 'Inativo' },
  { value: 'DELINQUENT', label: 'Negativado' },
  { value: 'SPECIAL', label: 'Especial' },
]

function toFormFields(clinic: Clinic | null): ClinicFormFields {
  return {
    name: clinic?.name ?? '',
    taxId: formatTaxId(clinic?.taxId ?? null) ?? '',
    phone: clinic?.phone ?? '',
    email: clinic?.email ?? '',
    status: clinic?.status ?? 'ACTIVE',
    addressZipCode: clinic?.addressZipCode ?? '',
    addressStreet: clinic?.addressStreet ?? '',
    addressNumber: clinic?.addressNumber ?? '',
    addressNeighborhood: clinic?.addressNeighborhood ?? '',
    addressCity: clinic?.addressCity ?? '',
    addressState: clinic?.addressState ?? '',
    addressComplement: clinic?.addressComplement ?? '',
    notes: clinic?.notes ?? '',
  }
}

function toApiValues(fields: ClinicFormFields): ClinicFormValues {
  return {
    name: fields.name,
    taxId: fields.taxId || null,
    phone: fields.phone || null,
    email: fields.email || null,
    addressZipCode: fields.addressZipCode || null,
    addressStreet: fields.addressStreet || null,
    addressNumber: fields.addressNumber || null,
    addressNeighborhood: fields.addressNeighborhood || null,
    addressCity: fields.addressCity || null,
    addressState: fields.addressState || null,
    addressComplement: fields.addressComplement || null,
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

interface ClinicFormProps {
  clinic: Clinic | null
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmitCreate?: (values: ClinicFormValues) => void
  onSubmitUpdate?: (values: ClinicFormValues & { status: ClinicStatus }) => void
}

export function ClinicForm({
  clinic,
  submitting,
  error,
  onCancel,
  onSubmitCreate,
  onSubmitUpdate,
}: ClinicFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ClinicFormFields>({
    resolver: zodResolver(clinicSchema),
    defaultValues: toFormFields(clinic),
  })

  const onSubmit = handleSubmit((fields) => {
    if (clinic) {
      onSubmitUpdate?.({ ...toApiValues(fields), status: fields.status })
    } else {
      onSubmitCreate?.(toApiValues(fields))
    }
  })

  const errorMessage = describeError(error)

  return (
    <form className="clinic-form" onSubmit={onSubmit} noValidate>
      <TextField
        id="clinic-name"
        label="Nome da clínica"
        disabled={submitting}
        errorMessage={errors.name?.message}
        {...register('name')}
      />

      <div className="clinic-form__row">
        <TextField id="clinic-tax-id" label="CNPJ" disabled={submitting} {...register('taxId')} />
        {clinic && (
          <SelectField
            id="clinic-status"
            label="Status"
            options={STATUS_OPTIONS}
            disabled={submitting}
            {...register('status')}
          />
        )}
      </div>

      <div className="clinic-form__row">
        <TextField
          id="clinic-phone"
          label="Telefone"
          disabled={submitting}
          {...register('phone')}
        />
        <TextField id="clinic-email" label="E-mail" disabled={submitting} {...register('email')} />
      </div>

      <p className="clinic-form__section-title">Endereço</p>

      <div className="clinic-form__row">
        <TextField
          id="clinic-zip"
          label="CEP"
          disabled={submitting}
          {...register('addressZipCode')}
        />
        <TextField
          id="clinic-street"
          label="Rua"
          disabled={submitting}
          {...register('addressStreet')}
        />
      </div>

      <div className="clinic-form__row">
        <TextField
          id="clinic-number"
          label="Número"
          disabled={submitting}
          {...register('addressNumber')}
        />
        <TextField
          id="clinic-neighborhood"
          label="Bairro"
          disabled={submitting}
          {...register('addressNeighborhood')}
        />
      </div>

      <div className="clinic-form__row">
        <TextField
          id="clinic-city"
          label="Cidade"
          disabled={submitting}
          {...register('addressCity')}
        />
        <TextField
          id="clinic-state"
          label="UF"
          maxLength={2}
          disabled={submitting}
          {...register('addressState')}
        />
      </div>

      <TextField
        id="clinic-complement"
        label="Complemento"
        disabled={submitting}
        {...register('addressComplement')}
      />

      <TextField id="clinic-notes" label="Observação" disabled={submitting} {...register('notes')} />

      {errorMessage && (
        <p role="alert" className="clinic-form__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="clinic-form__actions">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" className="clinic-form__submit" disabled={submitting}>
          {submitting ? 'Salvando…' : 'Salvar'}
        </Button>
      </div>
    </form>
  )
}
