import { Fragment, type ReactNode } from 'react'

import { KebabMenu, type KebabMenuItem } from '../../../shared/ui/kebab-menu'
import { Modal } from '../../../shared/ui/modal'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-row-popover.css'

export interface FeePopoverField {
  label: string
  value: ReactNode
}

interface FeeRowPopoverProps {
  titleId: string
  title: string
  /** Selo de status (Badge) e textos curtos ao lado, como no resumo do atendimento. */
  badge?: ReactNode
  sub?: string
  fields: FeePopoverField[]
  /** `pricing.manage`: libera o botão de edição. */
  canManage: boolean
  editLabel: string
  menuItems?: KebabMenuItem[]
  onEdit: () => void
  onClose: () => void
}

/** Resumo de uma taxa, aberto ao clicar na linha: mesmo popover do resumo de atendimento/exame. */
export function FeeRowPopover({
  titleId,
  title,
  badge,
  sub,
  fields,
  canManage,
  editLabel,
  menuItems = [],
  onEdit,
  onClose,
}: FeeRowPopoverProps) {
  return (
    <Modal
      size="md"
      dismissOnBackdrop
      className="attendance-popover"
      titleId={titleId}
      onClose={onClose}
    >
      <aside className="attendance-row-popover" aria-label={`Resumo: ${title}`}>
        <header className="attendance-row-popover__header">
          <div className="attendance-row-popover__heading">
            <h2 id={titleId} className="attendance-row-popover__title">
              {title}
            </h2>
            <div className="attendance-row-popover__sub">
              {badge}
              {sub && <span>{sub}</span>}
            </div>
          </div>
          <div className="attendance-row-popover__actions">
            {canManage && (
              <button
                type="button"
                className="button button--secondary attendance-row-popover__open"
                onClick={onEdit}
              >
                {editLabel}
              </button>
            )}
            {canManage && menuItems.length > 0 && (
              <KebabMenu label="Mais ações" items={menuItems} />
            )}
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
            {fields.map((field) => (
              <Fragment key={field.label}>
                <dt>{field.label}</dt>
                <dd>{field.value}</dd>
              </Fragment>
            ))}
          </dl>
        </div>
      </aside>
    </Modal>
  )
}
