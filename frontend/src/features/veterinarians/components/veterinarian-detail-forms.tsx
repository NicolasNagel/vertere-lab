import { useState } from 'react'

import { Checkbox } from '../../../shared/ui/checkbox'
import { Dropdown } from '../../../shared/ui/dropdown'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useLinkVeterinarianClinicMutation } from '../api/use-link-veterinarian-clinic-mutation'
import { useUnlinkVeterinarianClinicMutation } from '../api/use-unlink-veterinarian-clinic-mutation'
import { useUpdateVeterinarianMutation } from '../api/use-update-veterinarian-mutation'
import type {
  Veterinarian,
  VeterinarianFormValues,
  VeterinarianStatus,
} from '../api/veterinarians-api'
import {
  VeterinarianDetailError,
  VeterinarianDetailFooter,
  VeterinarianReasonField,
} from './veterinarian-detail-block'

interface FormProps {
  veterinarian: Veterinarian
  onClose: () => void
}

type Changes = Partial<VeterinarianFormValues & { status: VeterinarianStatus }>

/** O PATCH recebe o conjunto completo: o que o bloco não muda segue como está. */
function useVeterinarianCorrection({ veterinarian, onClose }: FormProps) {
  const [reason, setReason] = useState('')
  const mutation = useUpdateVeterinarianMutation()

  function save(changes: Changes) {
    mutation.mutate(
      {
        id: veterinarian.id,
        values: {
          name: veterinarian.name,
          crmv: veterinarian.crmv,
          phone: veterinarian.phone,
          email: veterinarian.email,
          isAutonomous: veterinarian.isAutonomous,
          notes: veterinarian.notes,
          status: veterinarian.status,
          ...changes,
          expectedRowVersion: veterinarian.rowVersion,
          reason: reason.trim(),
        },
      },
      { onSuccess: onClose },
    )
  }

  return { reason, setReason, mutation, save }
}

function Footer({
  veterinarian,
  api,
  canSave,
  onSave,
  onClose,
}: {
  veterinarian: Veterinarian
  api: ReturnType<typeof useVeterinarianCorrection>
  canSave: boolean
  onSave: () => void
  onClose: () => void
}) {
  return (
    <VeterinarianDetailFooter
      veterinarianId={veterinarian.id}
      reason={api.reason}
      onReasonChange={api.setReason}
      canSave={canSave}
      isPending={api.mutation.isPending}
      error={api.mutation.error}
      onSave={onSave}
      onCancel={onClose}
    />
  )
}

export function IdentityForm(props: FormProps) {
  const { veterinarian, onClose } = props
  const api = useVeterinarianCorrection(props)
  const [name, setName] = useState(veterinarian.name)
  const [crmv, setCrmv] = useState(veterinarian.crmv)
  const [notes, setNotes] = useState(veterinarian.notes ?? '')
  const changed =
    name.trim() !== veterinarian.name ||
    crmv.trim() !== veterinarian.crmv ||
    notes.trim() !== (veterinarian.notes ?? '')

  return (
    <div className="attendance-correction-block__form">
      <TextField
        id="veterinarian-edit-name"
        label="Nome"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <TextField
        id="veterinarian-edit-crmv"
        label="CRMV"
        value={crmv}
        onChange={(event) => setCrmv(event.target.value)}
      />
      <TextField
        id="veterinarian-edit-notes"
        label="Observação"
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
      />
      <Footer
        veterinarian={veterinarian}
        api={api}
        canSave={changed && name.trim().length > 0 && crmv.trim().length > 0}
        onClose={onClose}
        onSave={() =>
          api.save({
            name: name.trim(),
            crmv: crmv.trim(),
            notes: notes.trim() || null,
          })
        }
      />
    </div>
  )
}

export function ContactForm(props: FormProps) {
  const { veterinarian, onClose } = props
  const api = useVeterinarianCorrection(props)
  const [phone, setPhone] = useState(veterinarian.phone ?? '')
  const [email, setEmail] = useState(veterinarian.email ?? '')
  const changed =
    phone.trim() !== (veterinarian.phone ?? '') || email.trim() !== (veterinarian.email ?? '')

  return (
    <div className="attendance-correction-block__form">
      <TextField
        id="veterinarian-edit-phone"
        label="Telefone"
        value={phone}
        onChange={(event) => setPhone(event.target.value)}
      />
      <TextField
        id="veterinarian-edit-email"
        label="E-mail"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <Footer
        veterinarian={veterinarian}
        api={api}
        canSave={changed}
        onClose={onClose}
        onSave={() => api.save({ phone: phone.trim() || null, email: email.trim() || null })}
      />
    </div>
  )
}

export function StatusForm(props: FormProps) {
  const { veterinarian, onClose } = props
  const api = useVeterinarianCorrection(props)
  const [status, setStatus] = useState<VeterinarianStatus>(veterinarian.status)
  const [isAutonomous, setIsAutonomous] = useState(veterinarian.isAutonomous)

  return (
    <div className="attendance-correction-block__form">
      <Dropdown
        variant="field"
        label="Status"
        options={[
          { value: 'ACTIVE', label: 'Ativo' },
          { value: 'INACTIVE', label: 'Inativo' },
        ]}
        value={status}
        onChange={(value) => setStatus(value as VeterinarianStatus)}
      />
      <Checkbox
        label="Veterinário autônomo"
        checked={isAutonomous}
        onChange={(event) => setIsAutonomous(event.target.checked)}
      />
      <Footer
        veterinarian={veterinarian}
        api={api}
        canSave={status !== veterinarian.status || isAutonomous !== veterinarian.isAutonomous}
        onClose={onClose}
        onSave={() => api.save({ status, isAutonomous })}
      />
    </div>
  )
}

/** Vínculos com clínicas: cada vincular/remover é uma alteração própria e pede motivo. */
export function ClinicsForm({ veterinarian, onClose }: FormProps) {
  const [reason, setReason] = useState('')
  const [clinicId, setClinicId] = useState('')
  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const linkMutation = useLinkVeterinarianClinicMutation()
  const unlinkMutation = useUnlinkVeterinarianClinicMutation()

  const linked = new Set(veterinarian.clinics.map((clinic) => clinic.clinicId))
  const available = (clinicsQuery.data?.items ?? []).filter((clinic) => !linked.has(clinic.id))
  const pending = linkMutation.isPending || unlinkMutation.isPending
  const hasReason = reason.trim().length > 0

  return (
    <div className="attendance-correction-block__form">
      <ul className="attendance-readonly-detail__items">
        {veterinarian.clinics.map((clinic) => (
          <li
            key={clinic.clinicId}
            className="attendance-readonly-detail__item veterinarian-detail-page__edit-row"
          >
            <span>
              {clinic.clinicName}
              {clinic.primaryClinic ? ' · Principal' : ''}
            </span>
            <Button
              type="button"
              variant="cancel"
              aria-label={`Remover vínculo com ${clinic.clinicName}`}
              disabled={pending || !hasReason}
              onClick={() =>
                unlinkMutation.mutate({
                  veterinarianId: veterinarian.id,
                  clinicId: clinic.clinicId,
                  reason: reason.trim(),
                })
              }
            >
              Remover
            </Button>
          </li>
        ))}
        {veterinarian.clinics.length === 0 && (
          <li className="attendance-readonly-detail__item">Nenhuma clínica vinculada.</li>
        )}
      </ul>

      <VeterinarianReasonField
        veterinarianId={veterinarian.id}
        reason={reason}
        onReasonChange={setReason}
        disabled={pending}
      />

      {available.length > 0 && (
        <div className="attendance-correction-block__row">
          <Dropdown
            variant="field"
            label="Vincular clínica"
            placeholder="Selecione a clínica"
            options={available.map((clinic) => ({
              value: clinic.id,
              label: clinic.name,
            }))}
            searchable
            value={clinicId}
            disabled={pending}
            onChange={setClinicId}
          />
          <div className="attendance-correction-block__actions">
            <Button
              type="button"
              disabled={pending || !clinicId || !hasReason}
              onClick={() =>
                linkMutation.mutate(
                  {
                    veterinarianId: veterinarian.id,
                    clinicId,
                    reason: reason.trim(),
                    primary: veterinarian.clinics.length === 0,
                  },
                  { onSuccess: () => setClinicId('') },
                )
              }
            >
              Vincular
            </Button>
          </div>
        </div>
      )}

      <VeterinarianDetailError
        veterinarianId={veterinarian.id}
        error={linkMutation.error ?? unlinkMutation.error}
      />
      <div className="attendance-correction-block__actions">
        <Button type="button" variant="cancel" disabled={pending} onClick={onClose}>
          Concluir
        </Button>
      </div>
    </div>
  )
}
