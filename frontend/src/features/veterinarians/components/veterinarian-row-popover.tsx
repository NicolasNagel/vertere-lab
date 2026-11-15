import { Link } from 'react-router'

import { Badge } from '../../../shared/ui/badge'
import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import type { Veterinarian } from '../api/veterinarians-api'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-row-popover.css'
import './clinic-batch-picker.css'

export const VETERINARIAN_POPOVER_TITLE_ID = 'veterinarian-row-popover-title'

function displayValue(value: string | null): string {
  return value && value.trim().length > 0 ? value : '—'
}

interface VeterinarianRowPopoverProps {
  /** `null` enquanto o detalhe (com as clínicas vinculadas) carrega. */
  veterinarian: Veterinarian | null
  isLoading: boolean
  /** `veterinarians.manage`: libera "Inativar"; editar acontece nos blocos do detalhe. */
  canManage: boolean
  onClose: () => void
  onDeactivate: (id: string) => void
}

/** Resumo do veterinário, aberto ao clicar na linha — mesmo padrão do resumo de atendimento. */
export function VeterinarianRowPopover({
  veterinarian,
  isLoading,
  canManage,
  onClose,
  onDeactivate,
}: VeterinarianRowPopoverProps) {
  if (isLoading || !veterinarian) {
    return (
      <aside className="attendance-row-popover" aria-label="Resumo do veterinário">
        <p id={VETERINARIAN_POPOVER_TITLE_ID} className="attendance-row-popover__muted">
          {isLoading ? 'Carregando…' : 'Veterinário não encontrado.'}
        </p>
      </aside>
    )
  }

  const menuItems: KebabMenuItem[] =
    canManage && veterinarian.status === 'ACTIVE'
      ? [
          {
            label: 'Inativar veterinário',
            onSelect: () => onDeactivate(veterinarian.id),
            destructive: true,
          },
        ]
      : []

  return (
    <aside className="attendance-row-popover" aria-label="Resumo do veterinário">
      <header className="attendance-row-popover__header">
        <div className="attendance-row-popover__heading">
          <h2 id={VETERINARIAN_POPOVER_TITLE_ID} className="attendance-row-popover__title">
            {veterinarian.name}
          </h2>
          <div className="attendance-row-popover__sub">
            <Badge tone={veterinarian.status === 'ACTIVE' ? 'success' : 'neutral'}>
              {veterinarian.status === 'ACTIVE' ? 'Ativo' : 'Inativo'}
            </Badge>
            <span>{veterinarian.crmv}</span>
            {veterinarian.isAutonomous && <span>Autônomo</span>}
          </div>
        </div>
        <div className="attendance-row-popover__actions">
          <Link
            to={`/cadastros/veterinarios/${veterinarian.id}`}
            className="button button--secondary attendance-row-popover__open"
          >
            Abrir veterinário
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
        <dl className="attendance-row-popover__fields">
          <dt>Telefone</dt>
          <dd>{displayValue(veterinarian.phone)}</dd>
          <dt>E-mail</dt>
          <dd>{displayValue(veterinarian.email)}</dd>
          <dt>Observação</dt>
          <dd>{displayValue(veterinarian.notes)}</dd>
        </dl>

        <section aria-labelledby="veterinarian-row-popover-clinics">
          <h3 id="veterinarian-row-popover-clinics" className="attendance-row-popover__section">
            Clínicas vinculadas ({veterinarian.clinics.length})
          </h3>
          {veterinarian.clinics.length === 0 ? (
            <p className="attendance-row-popover__muted">
              {veterinarian.isAutonomous
                ? 'Autônomo: o vínculo com clínica é opcional.'
                : 'Nenhuma clínica vinculada ainda.'}
            </p>
          ) : (
            <ul className="attendance-row-popover__exams clinic-batch-picker__scroll">
              {veterinarian.clinics.map((clinic) => (
                <li key={clinic.clinicId}>
                  <span>
                    {clinic.clinicName}
                    {clinic.primaryClinic ? ' · Principal' : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </aside>
  )
}
