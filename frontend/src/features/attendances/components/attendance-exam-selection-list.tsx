import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { TextField } from '../../../shared/ui/text-field'
import type { Exam } from '../../catalog/api/catalog-api'
import type { DraftExamSelection } from '../api/use-attendance-exam-selections'
import { AttendanceExamCategoryTag } from './attendance-exam-category-tag'
import { ExamPicker } from './exam-picker'
import './attendance-exam-selection-list.css'

interface AttendanceExamSelectionListProps {
  selections: DraftExamSelection[]
  canOverridePrice: boolean
  disabled: boolean
  onAdd: (exam: Exam) => void
  onRemove: (examId: string) => void
  onUpdate: (examId: string, patch: Partial<DraftExamSelection>) => void
  /** Quando a seleção é feita por outra UI (grade de exames), esconde a busca. */
  hidePicker?: boolean
}

/** Lista de exames selecionados (com tag de categoria, preço, remoção,
 * quantidade e desconto opcional) + busca para adicionar mais — extraída
 * de `AttendanceConfirmationForm` para ser reaproveitada pela tela de
 * abertura de protocolo unificada. */
export function AttendanceExamSelectionList({
  selections,
  canOverridePrice,
  disabled,
  onAdd,
  onRemove,
  onUpdate,
  hidePicker = false,
}: AttendanceExamSelectionListProps) {
  return (
    <>
      {selections.length > 0 && (
        <ul className="attendance-exam-selection-list__items" aria-label="Exames selecionados">
          {selections.map((selection) => (
            <li key={selection.exam.id} className="attendance-exam-selection-list__item">
              <div className="attendance-exam-selection-list__item-main">
                <AttendanceExamCategoryTag examId={selection.exam.id} />
                <span className="attendance-exam-selection-list__item-name">
                  {selection.exam.name}
                </span>
                <span className="attendance-exam-selection-list__item-price">
                  {selection.exam.priceBase ? formatCurrencyBRL(selection.exam.priceBase) : '—'}
                </span>
                <button
                  type="button"
                  className="attendance-exam-selection-list__remove-button"
                  aria-label={`Remover ${selection.exam.name}`}
                  disabled={disabled}
                  onClick={() => onRemove(selection.exam.id)}
                >
                  ×
                </button>
              </div>
              <div className="attendance-exam-selection-list__item-fields">
                <TextField
                  id={`quantity-${selection.exam.id}`}
                  label="Quantidade"
                  type="number"
                  min={1}
                  disabled={disabled}
                  value={selection.quantity}
                  onChange={(event) =>
                    onUpdate(selection.exam.id, {
                      quantity: Math.max(1, Number(event.target.value) || 1),
                    })
                  }
                />
                {canOverridePrice && (
                  <>
                    <TextField
                      id={`discount-${selection.exam.id}`}
                      label="Desconto (R$)"
                      type="number"
                      min={0}
                      step="0.01"
                      disabled={disabled}
                      value={selection.discountAmount}
                      onChange={(event) =>
                        onUpdate(selection.exam.id, { discountAmount: event.target.value })
                      }
                    />
                    {Number(selection.discountAmount || 0) > 0 && (
                      <TextField
                        id={`override-reason-${selection.exam.id}`}
                        label="Motivo do desconto"
                        disabled={disabled}
                        value={selection.overrideReason}
                        errorMessage={
                          !selection.overrideReason.trim() ? 'Desconto exige motivo.' : undefined
                        }
                        onChange={(event) =>
                          onUpdate(selection.exam.id, { overrideReason: event.target.value })
                        }
                      />
                    )}
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {!hidePicker && (
        <ExamPicker
          disabled={disabled}
          excludeExamIds={selections.map((selection) => selection.exam.id)}
          onSelect={onAdd}
        />
      )}
    </>
  )
}
