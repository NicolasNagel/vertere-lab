import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { describeError } from '../../../shared/api/describe-error'
import { Checkbox } from '../../../shared/ui/checkbox'
import { TextField } from '../../../shared/ui/text-field'
import type { VeterinarianFormValues } from '../api/veterinarians-api'
import { ClinicBatchPicker } from './clinic-batch-picker'
import '../../attendances/components/attendance-draft-page.css'
import './veterinarian-form.css'

const optionalEmail = z.union([z.literal(''), z.email('Informe um e-mail válido.')])

const veterinarianSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome do veterinário.'),
  crmv: z.string().trim().min(1, 'Informe o CRMV.'),
  phone: z.string().trim(),
  email: optionalEmail,
  isAutonomous: z.boolean(),
  notes: z.string().trim(),
})

type VeterinarianFormFields = z.infer<typeof veterinarianSchema>

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

interface VeterinarianFormProps {
  submitting: boolean
  error?: unknown
  /** `id` do <form>, para o botão de salvar da barra inferior da tela. */
  formId: string
  onSubmitCreate: (
    values: VeterinarianFormValues,
    clinicIds: string[],
    primaryClinicId: string | null,
  ) => void
}

/** Cadastro de veterinário no layout do Novo Protocolo: blocos, e Cancelar | Salvar na barra
 * inferior da página. A edição acontece nos blocos do detalhe, com motivo. */
export function VeterinarianForm({
  submitting,
  error,
  formId,
  onSubmitCreate,
}: VeterinarianFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<VeterinarianFormFields>({
    resolver: zodResolver(veterinarianSchema),
    defaultValues: {
      name: '',
      crmv: '',
      phone: '',
      email: '',
      isAutonomous: false,
      notes: '',
    },
  })

  const isAutonomous = watch('isAutonomous')
  const [selectedClinicIds, setSelectedClinicIds] = useState<string[]>([])
  const [primaryClinicId, setPrimaryClinicId] = useState<string | null>(null)
  const [clinicsError, setClinicsError] = useState<string | null>(null)

  const onSubmit = handleSubmit((fields) => {
    if (!fields.isAutonomous && selectedClinicIds.length === 0) {
      setClinicsError('Selecione ao menos uma clínica ou marque como autônomo.')
      return
    }
    setClinicsError(null)
    onSubmitCreate(toApiValues(fields), selectedClinicIds, primaryClinicId)
  })

  const errorMessage = describeError(error)

  return (
    <form id={formId} onSubmit={onSubmit} noValidate>
      <div className="attendance-draft-page__stack">
        <section className="attendance-draft-page__section" aria-labelledby="vet-section-id">
          <h2 id="vet-section-id" className="attendance-draft-page__section-title">
            Identificação
          </h2>
          <div className="attendance-draft-page__row">
            <TextField
              id="veterinarian-name"
              label="Nome"
              disabled={submitting}
              errorMessage={errors.name?.message}
              {...register('name')}
            />
            <TextField
              id="veterinarian-crmv"
              label="CRMV"
              disabled={submitting}
              errorMessage={errors.crmv?.message}
              {...register('crmv')}
            />
          </div>
        </section>

        <section className="attendance-draft-page__section" aria-labelledby="vet-section-contact">
          <h2 id="vet-section-contact" className="attendance-draft-page__section-title">
            Contato
          </h2>
          <div className="attendance-draft-page__row">
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
              errorMessage={errors.email?.message}
              {...register('email')}
            />
          </div>
        </section>

        <section className="attendance-draft-page__section" aria-labelledby="vet-section-clinics">
          <h2 id="vet-section-clinics" className="attendance-draft-page__section-title">
            Clínicas vinculadas
          </h2>
          <Checkbox
            label="Veterinário autônomo"
            disabled={submitting}
            {...register('isAutonomous')}
          />
          <p className="veterinarian-form__hint">
            {isAutonomous
              ? 'Opcional para veterinário autônomo.'
              : 'Obrigatório para veterinário não autônomo.'}
          </p>
          <ClinicBatchPicker
            idPrefix="veterinarian-new"
            selectedIds={selectedClinicIds}
            primaryId={primaryClinicId}
            knownClinics={[]}
            disabled={submitting}
            onChange={(ids, primary) => {
              setSelectedClinicIds(ids)
              setPrimaryClinicId(primary)
            }}
          />
          {clinicsError && (
            <p role="alert" className="attendance-draft-page__domain-error">
              {clinicsError}
            </p>
          )}
        </section>

        <section className="attendance-draft-page__section" aria-labelledby="vet-section-notes">
          <h2 id="vet-section-notes" className="attendance-draft-page__section-title">
            Informações adicionais
          </h2>
          <TextField
            id="veterinarian-notes"
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
    </form>
  )
}
