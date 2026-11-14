import { useMemo, useState } from 'react'

import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { Checkbox } from '../../../shared/ui/checkbox'
import { SearchIcon } from '../../../shared/ui/icons'
import type { Exam, ExamCategory } from '../../catalog/api/catalog-api'
import './exam-cart-grid.css'

const PANEL_CATEGORY_NAME = 'perfis'

interface ExamCartGridProps {
  exams: Exam[]
  categories: ExamCategory[]
  selectedIds: string[]
  /** Quando há paciente, só aparecem exames da espécie dele. */
  patientSpeciesId: string | null
  isLoading: boolean
  isError: boolean
  disabled: boolean
  onAdd: (exam: Exam) => void
  onRemove: (examId: string) => void
}

function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

/** Grade de exames por categoria, como no formulário em papel: marcar um exame o põe no carrinho,
 * desmarcar o tira. Pacotes (perfis) e exames avulsos convivem; um exame avulso que já faz parte
 * de um pacote marcado ganha o aviso "incluso em …" (sem bloquear — repetir pode ser proposital). */
export function ExamCartGrid({
  exams,
  categories,
  selectedIds,
  patientSpeciesId,
  isLoading,
  isError,
  disabled,
  onAdd,
  onRemove,
}: ExamCartGridProps) {
  const [filter, setFilter] = useState('')

  const examById = useMemo(() => new Map(exams.map((exam) => [exam.id, exam])), [exams])

  const coveredBy = useMemo(() => {
    const map = new Map<string, string[]>()
    for (const id of selectedIds) {
      const panel = examById.get(id)
      if (!panel?.isPanel) continue
      for (const componentId of panel.componentExamIds) {
        map.set(componentId, [...(map.get(componentId) ?? []), panel.name])
      }
    }
    return map
  }, [selectedIds, examById])

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
                const checked = selectedIds.includes(exam.id)
                const includedIn = coveredBy.get(exam.id) ?? []
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
                          {exam.priceBase && (
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
                    {includedIn.length > 0 && (
                      <p
                        className="exam-cart-grid__covered"
                        data-duplicate={checked}
                        role={checked ? 'status' : undefined}
                      >
                        {checked ? 'Já incluso em ' : 'Incluso em '}
                        {includedIn.join(', ')}
                      </p>
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
