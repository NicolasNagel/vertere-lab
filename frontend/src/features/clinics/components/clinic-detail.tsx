import { Button } from '../../../shared/ui/button'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { formatTaxId } from '../../../shared/lib/formatters'
import type { Clinic, ClinicFormValues, ClinicStatus } from '../api/clinics-api'
import { ClinicForm } from './clinic-form'
import './clinic-detail.css'

const STATUS_LABELS: Record<Clinic['status'], string> = {
  ACTIVE: 'Ativo',
  INACTIVE: 'Inativo',
  DELINQUENT: 'Negativado',
  SPECIAL: 'Especial',
}

function displayValue(value: string | null): string {
  return value && value.trim().length > 0 ? value : '—'
}

interface ClinicDetailProps {
  clinic: Clinic | null
  isLoading: boolean
  isEditing: boolean
  canManage: boolean
  submitting: boolean
  submitError?: unknown
  onStartEdit: () => void
  onCancelEdit: () => void
  onSubmitUpdate: (values: ClinicFormValues & { status: ClinicStatus }) => void
  onDeactivate: () => void
}

export function ClinicDetail({
  clinic,
  isLoading,
  isEditing,
  canManage,
  submitting,
  submitError,
  onStartEdit,
  onCancelEdit,
  onSubmitUpdate,
  onDeactivate,
}: ClinicDetailProps) {
  if (isLoading) {
    return (
      <div className="clinic-detail">
        <p className="clinic-detail__empty">Carregando…</p>
      </div>
    )
  }

  if (!clinic) {
    return (
      <div className="clinic-detail">
        <p className="clinic-detail__empty">Selecione uma clínica na lista ao lado.</p>
      </div>
    )
  }

  if (isEditing) {
    return (
      <div className="clinic-detail">
        <ClinicForm
          clinic={clinic}
          submitting={submitting}
          error={submitError}
          onCancel={onCancelEdit}
          onSubmitUpdate={onSubmitUpdate}
        />
      </div>
    )
  }

  const menuItems: KebabMenuItem[] =
    clinic.status !== 'INACTIVE'
      ? [{ label: 'Inativar', onSelect: onDeactivate, destructive: true }]
      : []

  return (
    <div className="clinic-detail">
      <div className="clinic-detail__content">
        <div className="clinic-detail__header">
          <div>
            <div className="clinic-detail__title-row">
              <h2 className="clinic-detail__title">{clinic.name}</h2>
              <span className="clinic-detail__status" data-status={clinic.status}>
                {STATUS_LABELS[clinic.status]}
              </span>
            </div>
          </div>
          {canManage && (
            <div className="clinic-detail__actions">
              <Button
                type="button"
                variant="ghost"
                className="clinic-detail__edit"
                onClick={onStartEdit}
              >
                Editar
              </Button>
              {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}
            </div>
          )}
        </div>

        <div className="clinic-detail__cards">
          <div className="clinic-detail__card">
            <div className="clinic-detail__card-title">Dados gerais</div>
            <dl className="clinic-detail__fields">
              <dt>CNPJ</dt>
              <dd className="clinic-detail__mono">{displayValue(formatTaxId(clinic.taxId))}</dd>
              <dt>Telefone</dt>
              <dd className="clinic-detail__mono">{displayValue(clinic.phone)}</dd>
              <dt>E-mail</dt>
              <dd>{displayValue(clinic.email)}</dd>
              <dt>Observação</dt>
              <dd>{displayValue(clinic.notes)}</dd>
            </dl>
          </div>

          <div className="clinic-detail__card">
            <div className="clinic-detail__card-title">Endereço</div>
            <dl className="clinic-detail__fields">
              <dt>CEP</dt>
              <dd className="clinic-detail__mono">{displayValue(clinic.addressZipCode)}</dd>
              <dt>Rua</dt>
              <dd>{displayValue(clinic.addressStreet)}</dd>
              <dt>Número</dt>
              <dd>{displayValue(clinic.addressNumber)}</dd>
              <dt>Bairro</dt>
              <dd>{displayValue(clinic.addressNeighborhood)}</dd>
              <dt>Cidade / UF</dt>
              <dd>
                {clinic.addressCity
                  ? `${clinic.addressCity} / ${clinic.addressState ?? '—'}`
                  : '—'}
              </dd>
              <dt>Complemento</dt>
              <dd>{displayValue(clinic.addressComplement)}</dd>
            </dl>
          </div>
        </div>

        <div className="clinic-detail__vets">
          <div className="clinic-detail__vets-header">
            <span>Veterinários vinculados</span>
            <button
              type="button"
              className="clinic-detail__link-vet"
              disabled
              title="Vínculo é gerenciado a partir do cadastro do veterinário."
            >
              vincular novo
            </button>
          </div>
          {clinic.veterinarians.length === 0 ? (
            <p className="clinic-detail__vets-empty">Nenhum veterinário vinculado ainda.</p>
          ) : (
            <ul className="clinic-detail__vets-list">
              {clinic.veterinarians.map((veterinarian) => (
                <li key={veterinarian.veterinarianId} className="clinic-detail__vets-row">
                  <span className="clinic-detail__vets-name">{veterinarian.veterinarianName}</span>
                  <span className="clinic-detail__mono">{veterinarian.crmv}</span>
                  {veterinarian.primaryClinic && (
                    <span className="clinic-detail__vets-primary">Principal</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
