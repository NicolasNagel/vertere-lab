import { useState } from 'react'

import { useClinicsQuery } from '../../clinics/api/use-clinics-query'
import { Button } from '../../../shared/ui/button'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { SelectField } from '../../../shared/ui/select'
import { useLinkVeterinarianClinicMutation } from '../api/use-link-veterinarian-clinic-mutation'
import { useUnlinkVeterinarianClinicMutation } from '../api/use-unlink-veterinarian-clinic-mutation'
import type {
  Veterinarian,
  VeterinarianFormValues,
  VeterinarianStatus,
} from '../api/veterinarians-api'
import { VeterinarianForm } from './veterinarian-form'
import './veterinarian-detail.css'

const STATUS_LABELS: Record<Veterinarian['status'], string> = {
  ACTIVE: 'Ativo',
  INACTIVE: 'Inativo',
}

function displayValue(value: string | null): string {
  return value && value.trim().length > 0 ? value : '—'
}

interface VeterinarianClinicsCardProps {
  veterinarian: Veterinarian
  canManage: boolean
}

function VeterinarianClinicsCard({ veterinarian, canManage }: VeterinarianClinicsCardProps) {
  const [selectedClinicId, setSelectedClinicId] = useState('')
  const clinicsQuery = useClinicsQuery({ status: 'ACTIVE', pageSize: 100 })
  const linkMutation = useLinkVeterinarianClinicMutation()
  const unlinkMutation = useUnlinkVeterinarianClinicMutation()

  const linkedClinicIds = new Set(veterinarian.clinics.map((clinic) => clinic.clinicId))
  const availableClinics = (clinicsQuery.data?.items ?? []).filter(
    (clinic) => !linkedClinicIds.has(clinic.id),
  )

  function handleLink() {
    if (!selectedClinicId) return
    linkMutation.mutate(
      { veterinarianId: veterinarian.id, clinicId: selectedClinicId },
      { onSuccess: () => setSelectedClinicId('') },
    )
  }

  function handleUnlink(clinicId: string) {
    unlinkMutation.mutate({ veterinarianId: veterinarian.id, clinicId })
  }

  return (
    <div className="veterinarian-detail__clinics">
      <div className="veterinarian-detail__clinics-header">
        <span>Clínicas vinculadas</span>
      </div>

      {veterinarian.clinics.length === 0 ? (
        <p className="veterinarian-detail__clinics-empty">
          {veterinarian.isAutonomous
            ? 'Veterinário autônomo — vínculo com clínica é opcional.'
            : 'Nenhuma clínica vinculada ainda.'}
        </p>
      ) : (
        <ul className="veterinarian-detail__clinics-list">
          {veterinarian.clinics.map((clinic) => (
            <li key={clinic.clinicId} className="veterinarian-detail__clinics-row">
              <span className="veterinarian-detail__clinics-name">{clinic.clinicName}</span>
              {clinic.primaryClinic && (
                <span className="veterinarian-detail__clinics-primary">Principal</span>
              )}
              {canManage && (
                <button
                  type="button"
                  className="veterinarian-detail__unlink-clinic"
                  disabled={unlinkMutation.isPending}
                  onClick={() => handleUnlink(clinic.clinicId)}
                >
                  remover
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {canManage && availableClinics.length > 0 && (
        <div className="veterinarian-detail__clinics-add">
          <SelectField
            id="veterinarian-add-clinic"
            label="Vincular clínica"
            options={[
              { value: '', label: 'Selecione uma clínica…' },
              ...availableClinics.map((clinic) => ({ value: clinic.id, label: clinic.name })),
            ]}
            value={selectedClinicId}
            onChange={(event) => setSelectedClinicId(event.target.value)}
            disabled={linkMutation.isPending}
          />
          <Button
            type="button"
            variant="ghost"
            disabled={!selectedClinicId || linkMutation.isPending}
            onClick={handleLink}
          >
            Vincular
          </Button>
        </div>
      )}

      {linkMutation.isError && (
        <p role="alert" className="veterinarian-detail__clinics-error">
          Não foi possível vincular a clínica. Tente novamente.
        </p>
      )}

      {unlinkMutation.isError && (
        <p role="alert" className="veterinarian-detail__clinics-error">
          Não foi possível remover o vínculo. Veterinário não autônomo precisa de ao menos uma
          clínica.
        </p>
      )}
    </div>
  )
}

interface VeterinarianDetailProps {
  veterinarian: Veterinarian | null
  isLoading: boolean
  isEditing: boolean
  canManage: boolean
  submitting: boolean
  submitError?: unknown
  onStartEdit: () => void
  onCancelEdit: () => void
  onSubmitUpdate: (values: VeterinarianFormValues & { status: VeterinarianStatus }) => void
  onDeactivate: () => void
}

export function VeterinarianDetail({
  veterinarian,
  isLoading,
  isEditing,
  canManage,
  submitting,
  submitError,
  onStartEdit,
  onCancelEdit,
  onSubmitUpdate,
  onDeactivate,
}: VeterinarianDetailProps) {
  if (isLoading) {
    return (
      <div className="veterinarian-detail">
        <p className="veterinarian-detail__empty">Carregando…</p>
      </div>
    )
  }

  if (!veterinarian) {
    return (
      <div className="veterinarian-detail">
        <p className="veterinarian-detail__empty">Selecione um veterinário na lista ao lado.</p>
      </div>
    )
  }

  if (isEditing) {
    return (
      <div className="veterinarian-detail">
        <VeterinarianForm
          veterinarian={veterinarian}
          submitting={submitting}
          error={submitError}
          onCancel={onCancelEdit}
          onSubmitUpdate={onSubmitUpdate}
        />
      </div>
    )
  }

  const menuItems: KebabMenuItem[] =
    veterinarian.status !== 'INACTIVE'
      ? [{ label: 'Inativar', onSelect: onDeactivate, destructive: true }]
      : []

  return (
    <div className="veterinarian-detail">
      <div className="veterinarian-detail__content">
        <div className="veterinarian-detail__header">
          <div>
            <div className="veterinarian-detail__title-row">
              <h2 className="veterinarian-detail__title">{veterinarian.name}</h2>
              <span className="veterinarian-detail__status" data-status={veterinarian.status}>
                {STATUS_LABELS[veterinarian.status]}
              </span>
              {veterinarian.isAutonomous && (
                <span className="veterinarian-detail__autonomous">Autônomo</span>
              )}
            </div>
          </div>
          {canManage && (
            <div className="veterinarian-detail__actions">
              <Button
                type="button"
                variant="ghost"
                className="veterinarian-detail__edit"
                onClick={onStartEdit}
              >
                Editar
              </Button>
              {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}
            </div>
          )}
        </div>

        <div className="veterinarian-detail__cards">
          <div className="veterinarian-detail__card">
            <div className="veterinarian-detail__card-title">Dados gerais</div>
            <dl className="veterinarian-detail__fields">
              <dt>CRMV</dt>
              <dd className="veterinarian-detail__mono">{veterinarian.crmv}</dd>
              <dt>Telefone</dt>
              <dd className="veterinarian-detail__mono">{displayValue(veterinarian.phone)}</dd>
              <dt>E-mail</dt>
              <dd>{displayValue(veterinarian.email)}</dd>
              <dt>Observação</dt>
              <dd>{displayValue(veterinarian.notes)}</dd>
            </dl>
          </div>
        </div>

        <VeterinarianClinicsCard veterinarian={veterinarian} canManage={canManage} />
      </div>
    </div>
  )
}
