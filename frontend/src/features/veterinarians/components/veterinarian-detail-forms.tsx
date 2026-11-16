import { useMemo, useState } from 'react'

import { Checkbox } from '../../../shared/ui/checkbox'
import { Dropdown } from '../../../shared/ui/dropdown'
import { TextField } from '../../../shared/ui/text-field'
import { useUpdateVeterinarianClinicsMutation } from '../api/use-update-veterinarian-clinics-mutation'
import { useUpdateVeterinarianMutation } from '../api/use-update-veterinarian-mutation'
import type {
  Veterinarian,
  VeterinarianFormValues,
  VeterinarianStatus,
} from '../api/veterinarians-api'
import {
  VeterinarianDetailFooter,
} from './veterinarian-detail-block'
import { ClinicBatchPicker, MAX_CLINICS_PER_CHANGE } from './clinic-batch-picker'

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

/** Vínculos com clínicas em lote: marca quem entra e quem sai, e salva tudo de uma vez com um
 * motivo. O resumo "Vincular N · Desvincular M" mostra o efeito antes de salvar. */
export function ClinicsForm({ veterinarian, onClose }: FormProps) {
  const initialIds = useMemo(
    () => veterinarian.clinics.map((clinic) => clinic.clinicId),
    [veterinarian.clinics],
  )
  const initialPrimary = veterinarian.clinics.find((clinic) => clinic.primaryClinic)?.clinicId
  const [reason, setReason] = useState('')
  const [selectedIds, setSelectedIds] = useState<string[]>(initialIds)
  const [primaryId, setPrimaryId] = useState<string | null>(initialPrimary ?? initialIds[0] ?? null)
  const mutation = useUpdateVeterinarianClinicsMutation()

  const addIds = selectedIds.filter((id) => !initialIds.includes(id))
  const removeIds = initialIds.filter((id) => !selectedIds.includes(id))
  const primaryChanged = (primaryId ?? null) !== (initialPrimary ?? null) && selectedIds.length > 0
  const changed = addIds.length > 0 || removeIds.length > 0 || primaryChanged
  const needsAClinic = !veterinarian.isAutonomous && selectedIds.length === 0
  const overLimit =
    addIds.length > MAX_CLINICS_PER_CHANGE || removeIds.length > MAX_CLINICS_PER_CHANGE
  const canSave = changed && !needsAClinic && !overLimit

  function save() {
    mutation.mutate(
      {
        veterinarianId: veterinarian.id,
        change: {
          addClinicIds: addIds,
          removeClinicIds: removeIds,
          primaryClinicId: primaryId,
          expectedRowVersion: veterinarian.rowVersion,
          reason: reason.trim(),
        },
      },
      { onSuccess: onClose },
    )
  }

  return (
    <div className="attendance-correction-block__form">
      <ClinicBatchPicker
        idPrefix={`veterinarian-${veterinarian.id}`}
        selectedIds={selectedIds}
        primaryId={primaryId}
        knownClinics={veterinarian.clinics.map((clinic) => ({
          id: clinic.clinicId,
          name: clinic.clinicName,
        }))}
        disabled={mutation.isPending}
        onChange={(ids, primary) => {
          setSelectedIds(ids)
          setPrimaryId(primary)
        }}
      />
      <p className="clinic-batch-picker__diff" aria-live="polite">
        {changed
          ? `Vincular ${addIds.length} · Desvincular ${removeIds.length}${
              primaryChanged ? ' · Muda a clínica principal' : ''
            }`
          : 'Nenhuma alteração.'}
      </p>
      {needsAClinic && (
        <p role="alert" className="attendance-correction-block__error">
          Veterinário não autônomo precisa de ao menos uma clínica vinculada.
        </p>
      )}
      {overLimit && (
        <p role="alert" className="attendance-correction-block__error">
          Vincule ou desvincule no máximo {MAX_CLINICS_PER_CHANGE} clínicas por vez.
        </p>
      )}
      <VeterinarianDetailFooter
        veterinarianId={veterinarian.id}
        reason={reason}
        onReasonChange={setReason}
        canSave={canSave}
        isPending={mutation.isPending}
        error={mutation.error}
        onSave={save}
        onCancel={onClose}
      />
    </div>
  )
}
