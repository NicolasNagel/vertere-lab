import { useQueries } from '@tanstack/react-query'
import { useState } from 'react'

import { useDebouncedValue } from '../../../shared/lib/use-debounced-value'
import { CloseIcon, SearchIcon } from '../../../shared/ui/icons'
import { fetchExam } from '../api/catalog-api'
import { examQueryKey } from '../api/use-exam-query'
import { useExamsQuery } from '../api/use-exams-query'
import './panel-components-field.css'

interface PanelComponentsFieldProps {
  selectedIds: string[]
  disabled?: boolean
  errorMessage?: string | null
  onChange: (ids: string[]) => void
}

/** Escolha dos exames que formam um pacote/perfil. A ordem da lista é a ordem gravada. */
export function PanelComponentsField({
  selectedIds,
  disabled = false,
  errorMessage,
  onChange,
}: PanelComponentsFieldProps) {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebouncedValue(query, 300)

  const searchQuery = useExamsQuery({
    search: debouncedQuery.trim() || undefined,
    status: 'ACTIVE',
    pageSize: 10,
  })
  const selectedQueries = useQueries({
    queries: selectedIds.map((id) => ({
      queryKey: examQueryKey(id),
      queryFn: () => fetchExam(id),
    })),
  })

  const results = (searchQuery.data?.items ?? []).filter(
    (exam) => !exam.isPanel && !selectedIds.includes(exam.id),
  )

  function move(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= selectedIds.length) return
    const next = [...selectedIds]
    const [moved] = next.splice(index, 1)
    if (moved === undefined) return
    next.splice(target, 0, moved)
    onChange(next)
  }

  return (
    <div className="panel-components">
      <p className="panel-components__count" aria-live="polite">
        {selectedIds.length} exame{selectedIds.length === 1 ? '' : 's'} no pacote
      </p>

      {selectedIds.length > 0 && (
        <ol className="panel-components__list" aria-label="Exames do pacote">
          {selectedIds.map((id, index) => {
            const exam = selectedQueries[index]?.data
            const name = exam?.name ?? 'Carregando…'
            return (
              <li key={id} className="panel-components__item">
                <span className="panel-components__name">{name}</span>
                {exam && <span className="panel-components__code">{exam.code}</span>}
                <button
                  type="button"
                  aria-label={`Subir ${name}`}
                  disabled={disabled || index === 0}
                  onClick={() => move(index, -1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Descer ${name}`}
                  disabled={disabled || index === selectedIds.length - 1}
                  onClick={() => move(index, 1)}
                >
                  ↓
                </button>
                <button
                  type="button"
                  aria-label={`Remover ${name} do pacote`}
                  disabled={disabled}
                  onClick={() => onChange(selectedIds.filter((selectedId) => selectedId !== id))}
                >
                  <CloseIcon />
                </button>
              </li>
            )
          })}
        </ol>
      )}

      <label className="panel-components__search">
        <SearchIcon />
        <input
          type="search"
          placeholder="Buscar exame para incluir…"
          aria-label="Adicionar exame ao pacote"
          autoComplete="off"
          disabled={disabled}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>

      <div className="panel-components__results" role="listbox" aria-label="Exames encontrados">
        {searchQuery.isLoading && <p className="panel-components__hint">Buscando…</p>}
        {!searchQuery.isLoading && results.length === 0 && (
          <p className="panel-components__hint">Nenhum exame disponível.</p>
        )}
        {results.map((exam) => (
          <button
            key={exam.id}
            type="button"
            role="option"
            aria-selected={false}
            className="panel-components__result"
            disabled={disabled}
            onClick={() => {
              onChange([...selectedIds, exam.id])
              setQuery('')
            }}
          >
            <span>{exam.name}</span>
            <span className="panel-components__code">{exam.code}</span>
          </button>
        ))}
      </div>

      {errorMessage && (
        <p role="alert" className="panel-components__error">
          {errorMessage}
        </p>
      )}
    </div>
  )
}
