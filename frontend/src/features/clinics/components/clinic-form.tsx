import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { useCepLookupQuery } from '../../address-lookup/api/use-cep-lookup-query'
import { Button } from '../../../shared/ui/button'
import { Dropdown } from '../../../shared/ui/dropdown'
import { TagIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import { ApiError } from '../../../shared/api/errors'
import { formatCep, formatTaxId } from '../../../shared/lib/formatters'
import type { Clinic, ClinicFormValues, ClinicStatus } from '../api/clinics-api'
import '../../attendances/components/attendance-draft-page.css'
import './clinic-form.css'

const optionalEmail = z.union([z.literal(''), z.email('Informe um e-mail válido.')])

const clinicSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome da clínica.'),
  taxId: z
    .string()
    .trim()
    .refine(
      (value) => value === '' || value.replace(/\D/g, '').length === 14,
      'Informe um CNPJ com 14 dígitos.',
    ),
  phone: z.string().trim(),
  email: optionalEmail,
  status: z.enum(['ACTIVE', 'INACTIVE', 'DELINQUENT', 'SPECIAL']),
  addressZipCode: z
    .string()
    .trim()
    .refine(
      (value) => value === '' || value.replace(/\D/g, '').length === 8,
      'Informe um CEP com 8 dígitos.',
    ),
  addressStreet: z.string().trim(),
  addressNumber: z.string().trim(),
  addressNeighborhood: z.string().trim(),
  addressCity: z.string().trim(),
  addressState: z
    .string()
    .trim()
    .refine((value) => value === '' || /^[A-Za-z]{2}$/.test(value), 'Informe uma UF válida.'),
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
  /** `id` do <form>, para um botão de salvar fora dele (barra inferior da tela). */
  formId?: string
  hideActions?: boolean
  onCancel: () => void
  onSubmitCreate?: (values: ClinicFormValues) => void
  onSubmitUpdate?: (values: ClinicFormValues & { status: ClinicStatus }) => void
}

export function ClinicForm({
  clinic,
  submitting,
  error,
  formId,
  hideActions = false,
  onCancel,
  onSubmitCreate,
  onSubmitUpdate,
}: ClinicFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<ClinicFormFields>({
    resolver: zodResolver(clinicSchema),
    defaultValues: toFormFields(clinic),
  })

  // A consulta só dispara com 8 dígitos, então não precisa de debounce: busca assim que o CEP fecha.
  const cepLookup = useCepLookupQuery(watch('addressZipCode'))

  useEffect(() => {
    if (!cepLookup.data) return
    setValue('addressStreet', cepLookup.data.street ?? '', { shouldDirty: true })
    setValue('addressNeighborhood', cepLookup.data.neighborhood ?? '', { shouldDirty: true })
    setValue('addressCity', cepLookup.data.city ?? '', { shouldDirty: true })
    setValue('addressState', cepLookup.data.state ?? '', { shouldDirty: true })
  }, [cepLookup.data, setValue])

  const cepStatusMessage = cepLookup.isFetching
    ? 'Buscando endereço…'
    : cepLookup.data === null
      ? 'CEP não encontrado. Preencha o endereço manualmente.'
      : cepLookup.isError
        ? 'Não foi possível consultar o CEP. Preencha manualmente.'
        : null

  const onSubmit = handleSubmit((fields) => {
    if (clinic) {
      onSubmitUpdate?.({ ...toApiValues(fields), status: fields.status })
    } else {
      onSubmitCreate?.(toApiValues(fields))
    }
  })

  const errorMessage = describeError(error)

  return (
    <form className="clinic-form" id={formId} onSubmit={onSubmit} noValidate>
      <div className="attendance-draft-page__stack">
        <section className="attendance-draft-page__section" aria-labelledby="clinic-section-id">
          <h2 id="clinic-section-id" className="attendance-draft-page__section-title">
            Identificação
          </h2>
          <div className="clinic-form__grid">
            <TextField
              id="clinic-name"
              label="Nome da clínica"
              className="clinic-form__span-4"
              disabled={submitting}
              errorMessage={errors.name?.message}
              {...register('name')}
            />
            <TextField
              id="clinic-tax-id"
              label="CNPJ"
              className="clinic-form__span-2"
              disabled={submitting}
              errorMessage={errors.taxId?.message}
              {...register('taxId')}
            />
            {clinic && (
              <div className="clinic-form__span-2">
                <Dropdown
                  variant="field"
                  icon={<TagIcon />}
                  label="Status"
                  options={STATUS_OPTIONS}
                  value={watch('status')}
                  onChange={(value) => setValue('status', value as ClinicStatus, { shouldDirty: true })}
                  disabled={submitting}
                />
              </div>
            )}
          </div>
        </section>

        <section className="attendance-draft-page__section" aria-labelledby="clinic-section-contact">
          <h2 id="clinic-section-contact" className="attendance-draft-page__section-title">
            Contato
          </h2>
          <div className="clinic-form__grid">
            <TextField
              id="clinic-phone"
              label="Telefone"
              className="clinic-form__span-3"
              disabled={submitting}
              {...register('phone')}
            />
            <TextField
              id="clinic-email"
              label="E-mail"
              className="clinic-form__span-3"
              disabled={submitting}
              errorMessage={errors.email?.message}
              {...register('email')}
            />
          </div>
        </section>

        <section className="attendance-draft-page__section" aria-labelledby="clinic-section-address">
          <h2 id="clinic-section-address" className="attendance-draft-page__section-title">
            Endereço
          </h2>
          <div className="clinic-form__grid">
            <TextField
              id="clinic-zip"
              label="CEP"
              className="clinic-form__span-2"
              disabled={submitting}
              errorMessage={errors.addressZipCode?.message}
              inputMode="numeric"
              maxLength={9}
              {...register('addressZipCode', {
                onChange: (event) =>
                  setValue('addressZipCode', formatCep(event.target.value), {
                    shouldDirty: true,
                  }),
              })}
            />
            <TextField
              id="clinic-street"
              label="Rua"
              className="clinic-form__span-3"
              disabled={submitting}
              {...register('addressStreet')}
            />
            <TextField
              id="clinic-number"
              label="Número"
              className="clinic-form__span-1"
              disabled={submitting}
              {...register('addressNumber')}
            />
          </div>

          {cepStatusMessage && (
            <p role="status" aria-live="polite" className="clinic-form__cep-status">
              {cepStatusMessage}
            </p>
          )}

          <div className="clinic-form__grid">
            <TextField
              id="clinic-neighborhood"
              label="Bairro"
              className="clinic-form__span-2"
              disabled={submitting}
              {...register('addressNeighborhood')}
            />
            <TextField
              id="clinic-city"
              label="Cidade"
              className="clinic-form__span-3"
              disabled={submitting}
              {...register('addressCity')}
            />
            <TextField
              id="clinic-state"
              label="UF"
              className="clinic-form__span-1"
              maxLength={2}
              disabled={submitting}
              errorMessage={errors.addressState?.message}
              {...register('addressState')}
            />
            <TextField
              id="clinic-complement"
              label="Complemento"
              className="clinic-form__span-6"
              disabled={submitting}
              {...register('addressComplement')}
            />
          </div>
        </section>

        <section className="attendance-draft-page__section" aria-labelledby="clinic-section-notes">
          <h2 id="clinic-section-notes" className="attendance-draft-page__section-title">
            Informações adicionais
          </h2>
          <TextField
            id="clinic-notes"
            label="Observação"
            disabled={submitting}
            {...register('notes')}
          />
        </section>

        {errorMessage && (
          <p role="alert" className="attendance-draft-page__domain-error">
            {errorMessage}
          </p>
        )}
      </div>

      {!hideActions && (
        <div className="clinic-form__actions">
          <Button type="button" variant="cancel" onClick={onCancel} disabled={submitting}>
            Cancelar
          </Button>
          <Button type="submit" className="clinic-form__submit" disabled={submitting}>
            {submitting ? 'Salvando…' : 'Salvar'}
          </Button>
        </div>
      )}
    </form>
  )
}
