import { Link } from 'react-router'

import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { displayValue, formatTaxId } from '../../../shared/lib/formatters'
import type { Clinic } from '../api/clinics-api'
import { ClinicStatusBadge } from './clinic-status-badge'
import { ClinicVeterinariansList } from './clinic-veterinarians-list'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-list-page.css'
import '../../attendances/components/attendance-row-popover.css'
import './clinic-detail.css'

interface ClinicDetailProps {
  clinic: Clinic | null
  isLoading: boolean
  canManage: boolean
  onClose: () => void
  /** Falha de Inativar: o diálogo cobre a lista, então a mensagem aparece aqui. */
  actionError?: string | null
  onDeactivate: () => void
}

/** Conteúdo do popover de consulta (somente leitura) aberto ao clicar numa linha; editar abre a tela de formulário. */
export function ClinicDetail({
  clinic,
  isLoading,
  canManage,
  onClose,
  actionError,
  onDeactivate,
}: ClinicDetailProps) {
  if (isLoading || !clinic) {
    return (
      <aside className="attendance-row-popover" aria-label="Detalhes da clínica">
        <p id="clinic-detail-title" className="clinic-detail__empty">
          {isLoading ? 'Carregando…' : 'Clínica não encontrada.'}
        </p>
      </aside>
    )
  }

  const menuItems: KebabMenuItem[] =
    clinic.status !== 'INACTIVE'
      ? [{ label: 'Inativar', onSelect: onDeactivate, destructive: true }]
      : []

  return (
    <aside className="attendance-row-popover" aria-label="Detalhes da clínica">
      <header className="attendance-row-popover__header">
        <div className="attendance-row-popover__heading">
          <h2 id="clinic-detail-title" className="attendance-row-popover__title">{clinic.name}</h2>
          <div className="attendance-row-popover__sub">
            <ClinicStatusBadge status={clinic.status} />
            <span className="clinic-detail__mono">{displayValue(formatTaxId(clinic.taxId))}</span>
          </div>
        </div>
        <div className="attendance-row-popover__actions">
          {canManage && (
            <>
              <Link
                className="button button--secondary attendance-row-popover__open"
                to={`/cadastros/clinicas/${clinic.id}/editar`}
              >
                Editar
              </Link>
              {menuItems.length > 0 && <KebabMenu label="Mais ações" items={menuItems} />}
            </>
          )}
          <button
            type="button"
            className="attendance-row-popover__close"
            aria-label="Fechar detalhes"
            onClick={onClose}
          >
            ×
          </button>
        </div>
      </header>

      <div className="attendance-row-popover__body">
        {actionError && (
          <p role="alert" className="attendance-list-page__error">
            {actionError}
          </p>
        )}
        <section>
          <h3 className="attendance-row-popover__section">Contato</h3>
          <dl className="attendance-row-popover__fields">
            <dt>Telefone</dt>
            <dd className="clinic-detail__mono">{displayValue(clinic.phone)}</dd>
            <dt>E-mail</dt>
            <dd>{displayValue(clinic.email)}</dd>
            <dt>Observação</dt>
            <dd>{displayValue(clinic.notes)}</dd>
          </dl>
        </section>

        <section>
          <h3 className="attendance-row-popover__section">Endereço</h3>
          <dl className="attendance-row-popover__fields">
            <dt>CEP</dt>
            <dd className="clinic-detail__mono">{displayValue(clinic.addressZipCode)}</dd>
            <dt>Rua</dt>
            <dd>
              {displayValue(
                [clinic.addressStreet, clinic.addressNumber].filter(Boolean).join(', ') || null,
              )}
            </dd>
            <dt>Bairro</dt>
            <dd>{displayValue(clinic.addressNeighborhood)}</dd>
            <dt>Cidade / UF</dt>
            <dd>
              {clinic.addressCity ? `${clinic.addressCity} / ${clinic.addressState ?? '—'}` : '—'}
            </dd>
            <dt>Complemento</dt>
            <dd>{displayValue(clinic.addressComplement)}</dd>
          </dl>
        </section>

        <section>
          <h3 className="attendance-row-popover__section">
            Veterinários vinculados ({clinic.veterinarians.length})
          </h3>
          <ClinicVeterinariansList veterinarians={clinic.veterinarians} />
        </section>
      </div>
    </aside>
  )
}
