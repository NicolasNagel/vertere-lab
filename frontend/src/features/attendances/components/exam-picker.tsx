import { useState } from 'react'

import { useDebouncedValue } from '../../../shared/lib/use-debounced-value'
import { formatCurrencyBRL } from '../../../shared/lib/formatters'
import { SearchIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import { useExamsQuery } from '../../catalog/api/use-exams-query'
import type { Exam } from '../../catalog/api/catalog-api'
import './exam-picker.css'

interface ExamPickerProps {
  disabled?: boolean
  excludeExamIds: string[]
  onSelect: (exam: Exam) => void
}

export function ExamPicker({ disabled, excludeExamIds, onSelect }: ExamPickerProps) {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebouncedValue(query, 300)

  const examsQuery = useExamsQuery({
    search: debouncedQuery.trim() || undefined,
    status: 'ACTIVE',
    pageSize: 10,
  })

  const results = (examsQuery.data?.items ?? []).filter(
    (exam) => !excludeExamIds.includes(exam.id),
  )

  return (
    <div className="exam-picker">
      <TextField
        id="attendance-exam-search"
        label="Adicionar exame"
        icon={<SearchIcon />}
        placeholder="Buscar por nome ou código…"
        autoComplete="off"
        disabled={disabled}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />

      <div className="exam-picker__results" role="listbox" aria-label="Exames encontrados">
        {examsQuery.isLoading && <p className="exam-picker__hint">Buscando…</p>}

        {examsQuery.isError && (
          <p className="exam-picker__hint" role="alert">
            Não foi possível carregar os exames.{' '}
            <button type="button" onClick={() => void examsQuery.refetch()}>
              Tentar novamente
            </button>
          </p>
        )}

        {!examsQuery.isLoading && !examsQuery.isError && results.length === 0 && (
          <p className="exam-picker__hint">Nenhum exame ativo encontrado.</p>
        )}

        {results.map((exam) => (
          <button
            key={exam.id}
            type="button"
            role="option"
            aria-selected={false}
            className="exam-picker__result"
            disabled={disabled}
            onClick={() => {
              onSelect(exam)
              setQuery('')
            }}
          >
            <span className="exam-picker__result-name">{exam.name}</span>
            <span className="exam-picker__result-code">{exam.code}</span>
            <span className="exam-picker__result-price">
              {exam.priceBase ? formatCurrencyBRL(exam.priceBase) : '—'}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
