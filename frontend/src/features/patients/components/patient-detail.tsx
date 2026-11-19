import { displayValue } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import type { Patient, PatientFormValues, PatientStatus } from '../api/patients-api'
import { useSpeciesQuery } from '../api/use-species-query'
import { PatientForm } from './patient-form'
import { PATIENT_SEX_LABELS, PATIENT_STATUS_LABELS } from './patient-labels'
import './patient-detail.css'

interface PatientDetailProps {
  patient: Patient | null
  isLoading: boolean
  isEditing: boolean
  canManage: boolean
  submitting: boolean
  submitError?: unknown
  onStartEdit: () => void
  onCancelEdit: () => void
  onSubmitUpdate: (values: PatientFormValues & { status: PatientStatus }) => void
  onDeactivate: () => void
  onReactivate: () => void
}

export function PatientDetail({
  patient,
  isLoading,
  isEditing,
  canManage,
  submitting,
  submitError,
  onStartEdit,
  onCancelEdit,
  onSubmitUpdate,
  onDeactivate,
  onReactivate,
}: PatientDetailProps) {
  const speciesQuery = useSpeciesQuery()

  if (isLoading) {
    return (
      <div className="patient-detail">
        <p className="patient-detail__empty">Carregando…</p>
      </div>
    )
  }

  if (!patient) {
    return (
      <div className="patient-detail">
        <p className="patient-detail__empty">Paciente não encontrado.</p>
      </div>
    )
  }

  if (isEditing) {
    return (
      <div className="patient-detail">
        <PatientForm
          patient={patient}
          submitting={submitting}
          error={submitError}
          onCancel={onCancelEdit}
          onSubmitUpdate={onSubmitUpdate}
        />
      </div>
    )
  }

  const speciesName =
    speciesQuery.data?.find((species) => species.id === patient.speciesId)?.name ?? '—'

  const menuItems: KebabMenuItem[] =
    patient.status !== 'INACTIVE'
      ? [{ label: 'Inativar', onSelect: onDeactivate, destructive: true }]
      : []

  return (
    <div className="patient-detail">
      <div className="patient-detail__content">
        <div className="patient-detail__header">
          <div>
            <div className="patient-detail__title-row">
              <h2 className="patient-detail__title">{patient.name}</h2>
              <span className="patient-detail__status" data-status={patient.status}>
                {PATIENT_STATUS_LABELS[patient.status]}
              </span>
            </div>
          </div>
          {canManage && (
            <div className="patient-detail__actions">
              {patient.status === 'INACTIVE' ? (
                <Button type="button" variant="secondary" onClick={onReactivate}>
                  Reativar
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="ghost"
                  className="patient-detail__edit"
                  onClick={onStartEdit}
                >
                  Editar
                </Button>
              )}
              {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}
            </div>
          )}
        </div>

        <div className="patient-detail__cards">
          <div className="patient-detail__card">
            <div className="patient-detail__card-title">Dados gerais</div>
            <dl className="patient-detail__fields">
              <dt>Espécie</dt>
              <dd>{speciesName}</dd>
              <dt>Raça</dt>
              <dd>{displayValue(patient.breed)}</dd>
              <dt>Sexo</dt>
              <dd>{PATIENT_SEX_LABELS[patient.sex]}</dd>
              <dt>Idade</dt>
              <dd>{displayValue(patient.ageDescription)}</dd>
              <dt>Observação</dt>
              <dd>{displayValue(patient.notes)}</dd>
            </dl>
          </div>

          <div className="patient-detail__card">
            <div className="patient-detail__card-title">Tutor</div>
            <dl className="patient-detail__fields">
              <dt>Nome</dt>
              <dd>{patient.ownerName}</dd>
              <dt>Telefone</dt>
              <dd className="patient-detail__mono">{displayValue(patient.ownerPhone)}</dd>
              <dt>Documento</dt>
              <dd className="patient-detail__mono">{displayValue(patient.ownerDocument)}</dd>
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
