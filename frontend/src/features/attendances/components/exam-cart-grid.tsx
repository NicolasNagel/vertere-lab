import { useMemo, useState } from 'react'

import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { Checkbox } from '../../../shared/ui/checkbox'
import { SearchIcon } from '../../../shared/ui/icons'
import type { Exam, ExamCategory } from '../../catalog/api/catalog-api'
import type { DraftExamSelection } from '../api/use-attendance-exam-selections'
import './exam-cart-grid.css'

const PANEL_CATEGORY_NAME = 'perfis'

interface ExamCartGridProps {
  exams: Exam[]
  categories: ExamCategory[]
  selections: DraftExamSelection[]
  /** `pricing.read`: sem ele a grade não mostra preço nem desconto. */
  showMoney: boolean
  /** `attendances.override_price`: só quem pode aplica desconto por exame. */
  canDiscount: boolean
  /** Quando há paciente, só aparecem exames da espécie dele. */
  patientSpeciesId: string | null
  isLoading: boolean
  isError: boolean
  disabled: boolean
  onAdd: (exam: Exam) => void
  onRemove: (examId: string) => void
  onUpdate: (examId: string, patch: Partial<DraftExamSelection>) => void
}

function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

/** Grade de exames por categoria, como no formulário em papel: marcar um exame o põe no carrinho,
 * desmarcar o tira. Exame marcado mostra, na própria linha, quantidade e (com permissão) desconto
 * em valor livre, limitado ao valor da linha. Repetir exame que já está num pacote é livre. */
export function ExamCartGrid({
  exams,
  categories,
  selections,
  showMoney,
  canDiscount,
  patientSpeciesId,
  isLoading,
  isError,
  disabled,
  onAdd,
  onRemove,
  onUpdate,
}: ExamCartGridProps) {
  const [filter, setFilter] = useState('')

  const examById = useMemo(() => new Map(exams.map((exam) => [exam.id, exam])), [exams])

  const selectionById = useMemo(
    () => new Map(selections.map((selection) => [selection.exam.id, selection])),
    [selections],
  )

  const groups = useMemo(() => {
    const needle = normalize(filter.trim())
    const visible = exams.filter(
      (exam) =>
        (patientSpeciesId === null || exam.speciesIds.includes(patientSpeciesId)) &&
        (needle === '' || normalize(exam.name).includes(needle)),
    )
    const ordered = [...categories].sort((a, b) => {
      const aPanel = a.name.toLowerCase() === PANEL_CATEGORY_NAME
      const bPanel = b.name.toLowerCase() === PANEL_CATEGORY_NAME
      if (aPanel !== bPanel) return aPanel ? -1 : 1
      return a.name.localeCompare(b.name, 'pt-BR')
    })
    return ordered
      .map((category) => ({
        category,
        items: visible
          .filter((exam) => exam.categoryId === category.id)
          .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR', { numeric: true })),
      }))
      .filter((group) => group.items.length > 0)
  }, [exams, categories, filter, patientSpeciesId])

  if (isLoading) return <p className="exam-cart-grid__hint">Carregando exames…</p>
  if (isError) {
    return (
      <p role="alert" className="exam-cart-grid__hint">
        Não foi possível carregar os exames.
      </p>
    )
  }

  return (
    <div className="exam-cart-grid">
      <label className="exam-cart-grid__filter">
        <SearchIcon />
        <input
          type="search"
          placeholder="Filtrar exames…"
          aria-label="Filtrar exames"
          autoComplete="off"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
      </label>

      {groups.length === 0 && <p className="exam-cart-grid__hint">Nenhum exame encontrado.</p>}

      {groups.map(({ category, items }) => {
        const isPanelGroup = category.name.toLowerCase() === PANEL_CATEGORY_NAME
        return (
          <section key={category.id} className="exam-cart-grid__group" aria-label={category.name}>
            <h3 className="exam-cart-grid__group-title">{category.name}</h3>
            <ul className="exam-cart-grid__list" data-panels={isPanelGroup}>
              {items.map((exam) => {
                const selection = selectionById.get(exam.id)
                const checked = selection !== undefined
                const composition = exam.isPanel
                  ? exam.componentExamIds
                      .map((id) => examById.get(id)?.name)
                      .filter((name): name is string => Boolean(name))
                      .join(', ')
                  : ''
                return (
                  <li key={exam.id} className="exam-cart-grid__item" data-checked={checked}>
                    <Checkbox
                      label={
                        <span className="exam-cart-grid__label">
                          <span className="exam-cart-grid__name">{exam.name}</span>
                          {showMoney && exam.priceBase && (
                            <span className="exam-cart-grid__price">
                              {formatCurrencyBRL(exam.priceBase)}
                            </span>
                          )}
                        </span>
                      }
                      checked={checked}
                      disabled={disabled}
                      onChange={() => (checked ? onRemove(exam.id) : onAdd(exam))}
                    />
                    {composition && <p className="exam-cart-grid__composition">{composition}</p>}
                    {selection && (
                      <ExamLineFields
                        selection={selection}
                        showMoney={showMoney}
                        canDiscount={canDiscount}
                        disabled={disabled}
                        onUpdate={onUpdate}
                      />
                    )}
                  </li>
                )
              })}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

interface ExamLineFieldsProps {
  selection: DraftExamSelection
  showMoney: boolean
  canDiscount: boolean
  disabled: boolean
  onUpdate: (examId: string, patch: Partial<DraftExamSelection>) => void
}

/** Quantidade e desconto do exame marcado. O desconto nunca passa do valor da linha. */
function ExamLineFields({ selection, showMoney, canDiscount, disabled, onUpdate }: ExamLineFieldsProps) {
  const { exam } = selection
  const lineTotal = exam.priceBase ? Number(exam.priceBase) * selection.quantity : null
  const discount = Number(selection.discountAmount || 0)
  const showDiscount = showMoney && canDiscount

  function handleDiscountChange(raw: string) {
    const value = Number(raw)
    if (raw !== '' && lineTotal !== null && value > lineTotal) {
      onUpdate(exam.id, { discountAmount: lineTotal.toFixed(2) })
      return
    }
    onUpdate(exam.id, { discountAmount: raw })
  }

  return (
    <div className="exam-cart-grid__line-fields">
      <label className="exam-cart-grid__mini-field">
        <span>Qtd.</span>
        <input
          type="number"
          min={1}
          inputMode="numeric"
          disabled={disabled}
          value={selection.quantity}
          aria-label={`Quantidade de ${exam.name}`}
          onChange={(event) =>
            onUpdate(exam.id, { quantity: Math.max(1, Math.floor(Number(event.target.value)) || 1) })
          }
        />
      </label>
      {showDiscount && (
        <>
          <label className="exam-cart-grid__mini-field">
            <span>Desconto (R$)</span>
            <input
              type="number"
              min={0}
              max={lineTotal ?? undefined}
              step="0.01"
              inputMode="decimal"
              disabled={disabled}
              value={selection.discountAmount}
              aria-label={`Desconto de ${exam.name}`}
              onChange={(event) => handleDiscountChange(event.target.value)}
            />
          </label>
          {discount > 0 && (
            <label className="exam-cart-grid__mini-field exam-cart-grid__mini-field--wide">
              <span>Motivo</span>
              <input
                type="text"
                disabled={disabled}
                value={selection.overrideReason}
                aria-label={`Motivo do desconto de ${exam.name}`}
                aria-invalid={!selection.overrideReason.trim()}
                onChange={(event) => onUpdate(exam.id, { overrideReason: event.target.value })}
              />
            </label>
          )}
        </>
      )}
    </div>
  )
}
