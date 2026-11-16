import { useEffect, useState } from 'react'

import { Checkbox } from '../../../shared/ui/checkbox'
import { CloseIcon } from '../../../shared/ui/icons'
import { Pagination } from '../../../shared/ui/pagination'
import { TextField } from '../../../shared/ui/text-field'
import { useExamNames } from '../api/use-exam-names'
import { useExamsQuery } from '../api/use-exams-query'
import './fees.css'

/** A API recusa mais exames que isso numa única regra. */
export const MAX_EXAMS_PER_RULE = 50
const PAGE_SIZE = 8

interface ExamConditionPickerProps {
  idPrefix: string
  examIds: string[]
  onChange: (examIds: string[]) => void
}

function useDebounced(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

/** Escolha de exames da condição: busca no servidor, páginas e chips. Serve para 8 ou 800
 * exames no catálogo; o nome dos já escolhidos vem por id, mesmo fora da página mostrada. */
export function ExamConditionPicker({ idPrefix, examIds, onChange }: ExamConditionPickerProps) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const debouncedSearch = useDebounced(search.trim(), 300)
  const query = useExamsQuery({
    search: debouncedSearch || undefined,
    status: 'ACTIVE',
    page,
    pageSize: PAGE_SIZE,
  })
  const pageItems = query.data?.items ?? []
  const total = query.data?.total ?? 0

  const [pageNames, setPageNames] = useState<Map<string, string>>(new Map())
  useEffect(() => {
    if (!query.data?.items.length) return
    setPageNames((current) => {
      const next = new Map(current)
      for (const exam of query.data.items) next.set(exam.id, exam.name)
      return next
    })
  }, [query.data])
  // Exames já escolhidos que a busca atual não trouxe (ex.: regra aberta para edição).
  const missing = examIds.filter((id) => !pageNames.has(id))
  const fetchedNames = useExamNames(missing)
  const nameOf = (id: string) => pageNames.get(id) ?? fetchedNames.get(id) ?? 'Exame'

  const selected = new Set(examIds)
  const atLimit = examIds.length >= MAX_EXAMS_PER_RULE

  function toggle(id: string) {
    onChange(selected.has(id) ? examIds.filter((item) => item !== id) : [...examIds, id])
  }

  return (
    <div className="fees__exam-picker">
      <TextField
        id={`${idPrefix}-exam-search`}
        label="Buscar exame"
        placeholder="Nome ou código do exame"
        value={search}
        onChange={(event) => {
          setSearch(event.target.value)
          setPage(1)
        }}
      />
      <div className="fees__exam-list" role="group" aria-label="Exames disponíveis">
        {query.isLoading && <p className="fees__note">Carregando exames…</p>}
        {query.isError && (
          <p role="alert" className="fees__note fees__note--error">
            Não foi possível carregar os exames.
          </p>
        )}
        {!query.isLoading && !query.isError && pageItems.length === 0 && (
          <p className="fees__note">Nenhum exame encontrado.</p>
        )}
        {pageItems.map((exam) => (
          <Checkbox
            key={exam.id}
            label={exam.name}
            checked={selected.has(exam.id)}
            disabled={atLimit && !selected.has(exam.id)}
            onChange={() => toggle(exam.id)}
          />
        ))}
      </div>
      <Pagination
        itemLabel={['exame', 'exames']}
        page={query.data?.page ?? page}
        pageSize={PAGE_SIZE}
        total={total}
        onPageChange={setPage}
      />
      <p className="fees__note" aria-live="polite">
        {examIds.length === 1 ? '1 exame selecionado' : `${examIds.length} exames selecionados`}
        {` (máximo ${MAX_EXAMS_PER_RULE})`}
      </p>
      {atLimit && (
        <p role="alert" className="fees__note fees__note--error">
          Limite de {MAX_EXAMS_PER_RULE} exames por taxa. Remova algum para adicionar outro.
        </p>
      )}
      {examIds.length > 0 && (
        <ul
          className="fees__tags fees__tags--scroll"
          aria-label="Exames da condição"
          id={`${idPrefix}-exams`}
          tabIndex={0}
        >
          {examIds.map((id) => (
            <li key={id} className="fees__tag">
              {nameOf(id)}
              <button
                type="button"
                className="fees__tag-remove"
                aria-label={`Remover ${nameOf(id)}`}
                onClick={() => toggle(id)}
              >
                <CloseIcon />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
