import { Link } from 'react-router'

import { Badge } from '../../../shared/ui/badge'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import type { Patient } from '../api/patients-api'
import {
  displayValue,
  PATIENT_SEX_LABELS,
  PATIENT_STATUS_LABELS,
  patientLoadErrorMessage,
} from './patient-labels'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-row-popover.css'

export const PATIENT_POPOVER_TITLE_ID = 'patient-row-popover-title'

interface PatientRowPopoverProps {
  /** `null` enquanto o detalhe carrega (ou se o paciente não existe/está fora do escopo). */
  patient: Patient | null
  isLoading: boolean
  /** Erro do carregamento do detalhe, para separar 403 de "não encontrado". */
  loadError?: unknown
  speciesName: string
  clinicName: string
  /** `patients.manage`: libera Inativar/Reativar; editar acontece na tela do paciente. */
  canManage: boolean
  onClose: () => void
  onDeactivate: (id: string) => void
  onReactivate: (id: string) => void
}

/** Resumo do paciente, aberto ao clicar na linha — mesmo padrão do resumo de atendimento. */
export function PatientRowPopover({
  patient,
  isLoading,
  loadError,
  speciesName,
  clinicName,
  canManage,
  onClose,
  onDeactivate,
  onReactivate,
}: PatientRowPopoverProps) {
  if (isLoading || !patient) {
    return (
      <aside className="attendance-row-popover" aria-label="Resumo do paciente">
        <p id={PATIENT_POPOVER_TITLE_ID} className="attendance-row-popover__muted">
          {isLoading ? 'Carregando…' : patientLoadErrorMessage(loadError)}
        </p>
      </aside>
    )
  }

  const menuItems: KebabMenuItem[] = canManage
    ? patient.status === 'ACTIVE'
      ? [
          {
            label: 'Inativar paciente',
            onSelect: () => onDeactivate(patient.id),
            destructive: true,
          },
        ]
      : [{ label: 'Reativar paciente', onSelect: () => onReactivate(patient.id) }]
    : []

  return (
    <aside className="attendance-row-popover" aria-label="Resumo do paciente">
      <header className="attendance-row-popover__header">
        <div className="attendance-row-popover__heading">
          <h2 id={PATIENT_POPOVER_TITLE_ID} className="attendance-row-popover__title">
            {patient.name}
          </h2>
          <div className="attendance-row-popover__sub">
            <Badge tone={patient.status === 'ACTIVE' ? 'success' : 'neutral'}>
              {PATIENT_STATUS_LABELS[patient.status]}
            </Badge>
            <span>{speciesName}</span>
          </div>
        </div>
        <div className="attendance-row-popover__actions">
          <Link
            to={`/pacientes/${patient.id}`}
            className="button button--secondary attendance-row-popover__open"
          >
            Abrir paciente
          </Link>
          {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}
          <button
            type="button"
            className="attendance-row-popover__close"
            aria-label="Fechar resumo"
            onClick={onClose}
          >
            ×
          </button>
        </div>
      </header>

      <div className="attendance-row-popover__body">
        <section aria-labelledby="patient-row-popover-data">
          <h3 id="patient-row-popover-data" className="attendance-row-popover__section">
            Dados gerais
          </h3>
          <dl className="attendance-row-popover__fields">
            <dt>Raça</dt>
            <dd>{displayValue(patient.breed)}</dd>
            <dt>Sexo</dt>
            <dd>{PATIENT_SEX_LABELS[patient.sex]}</dd>
            <dt>Idade</dt>
            <dd>{displayValue(patient.ageDescription)}</dd>
            <dt>Clínica</dt>
            <dd>{clinicName}</dd>
            <dt>Observação</dt>
            <dd>{displayValue(patient.notes)}</dd>
          </dl>
        </section>

        <section aria-labelledby="patient-row-popover-owner">
          <h3 id="patient-row-popover-owner" className="attendance-row-popover__section">
            Tutor
          </h3>
          <dl className="attendance-row-popover__fields">
            <dt>Nome</dt>
            <dd>{patient.ownerName}</dd>
            <dt>Telefone</dt>
            <dd>{displayValue(patient.ownerPhone)}</dd>
            <dt>Documento</dt>
            <dd>{displayValue(patient.ownerDocument)}</dd>
          </dl>
        </section>
      </div>
    </aside>
  )
}
