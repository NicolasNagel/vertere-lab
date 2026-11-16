import { useEffect, useMemo, useState } from 'react'

import { fetchAllPages } from '../../../shared/api/fetch-all-pages'
import { Button } from '../../../shared/ui/button'
import { Checkbox } from '../../../shared/ui/checkbox'
import { Dropdown } from '../../../shared/ui/dropdown'
import { CloseIcon } from '../../../shared/ui/icons'
import { Pagination } from '../../../shared/ui/pagination'
import { TextField } from '../../../shared/ui/text-field'
import { fetchClinics, type Clinic, type ClinicListParams } from '../../clinics/api/clinics-api'
import { useClinicsQuery } from '../../clinics/api/use-clinics-query'
import './clinic-batch-picker.css'

/** O backend recusa mais que isso por chamada; a seleção em massa respeita o mesmo teto. */
export const MAX_CLINICS_PER_CHANGE = 500
const PAGE_SIZE = 10
const SELECTED_FILTER_THRESHOLD = 8

export interface KnownClinic {
  id: string
  name: string
}

interface ClinicBatchPickerProps {
  idPrefix: string
  selectedIds: string[]
  primaryId: string | null
  /** Clínicas já conhecidas (ex.: as vinculadas hoje), para mostrar o nome sem buscar de novo. */
  knownClinics: KnownClinic[]
  disabled?: boolean
  onChange: (selectedIds: string[], primaryId: string | null) => void
}

function useDebounced(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

/** Escolha de várias clínicas de uma vez: busca no servidor, páginas, seleção em massa, chips e
 * uma única clínica principal. Serve para 3 ou para 300 clínicas. */
export function ClinicBatchPicker({
  idPrefix,
  selectedIds,
  primaryId,
  knownClinics,
  disabled = false,
  onChange,
}: ClinicBatchPickerProps) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selectedFilter, setSelectedFilter] = useState('')
  const [names, setNames] = useState<Map<string, string>>(
    () => new Map(knownClinics.map((clinic) => [clinic.id, clinic.name])),
  )
  const [bulkState, setBulkState] = useState<'idle' | 'loading' | 'too-many' | 'error'>('idle')

  const debouncedSearch = useDebounced(search.trim(), 300)
  const query = useClinicsQuery({
    search: debouncedSearch || undefined,
    status: 'ACTIVE',
    page,
    pageSize: PAGE_SIZE,
  })
  const pageItems = query.data?.items
  const total = query.data?.total ?? 0

  useEffect(() => {
    if (!pageItems?.length) return
    setNames((current) => {
      const next = new Map(current)
      for (const clinic of pageItems) next.set(clinic.id, clinic.name)
      return next
    })
  }, [pageItems])

  const selected = useMemo(() => new Set(selectedIds), [selectedIds])
  const nameOf = (id: string) => names.get(id) ?? 'Clínica'

  function update(nextIds: string[], nextPrimary: string | null = primaryId) {
    const primary = nextPrimary && nextIds.includes(nextPrimary) ? nextPrimary : (nextIds[0] ?? null)
    onChange(nextIds, primary)
  }

  function toggle(clinicId: string) {
    if (selected.has(clinicId)) update(selectedIds.filter((id) => id !== clinicId))
    else update([...selectedIds, clinicId])
  }

  async function selectAllFiltered() {
    setBulkState('loading')
    try {
      const all = await fetchAllPages<Clinic, ClinicListParams>(fetchClinics, {
        search: debouncedSearch || undefined,
        status: 'ACTIVE',
      })
      const merged = new Set(selectedIds)
      const nextNames = new Map(names)
      for (const clinic of all.items) {
        merged.add(clinic.id)
        nextNames.set(clinic.id, clinic.name)
      }
      if (merged.size > MAX_CLINICS_PER_CHANGE) {
        setBulkState('too-many')
        return
      }
      setNames(nextNames)
      update([...merged])
      setBulkState('idle')
    } catch {
      setBulkState('error')
    }
  }

  const visibleSelected = useMemo(() => {
    const term = normalize(selectedFilter.trim())
    if (!term) return selectedIds
    return selectedIds.filter((id) => normalize(nameOf(id)).includes(term))
    // nameOf depende de `names`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIds, selectedFilter, names])

  const searchId = `${idPrefix}-clinic-search`
  const filterId = `${idPrefix}-selected-filter`

  return (
    <div className="clinic-batch-picker">
      <div className="clinic-batch-picker__toolbar">
        <div className="clinic-batch-picker__search">
          <TextField
            id={searchId}
            label="Buscar clínica"
            placeholder="Nome da clínica"
            value={search}
            disabled={disabled}
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
              setBulkState('idle')
            }}
          />
        </div>
        <div className="clinic-batch-picker__bulk">
          <Button
            type="button"
            variant="secondary"
            disabled={disabled || bulkState === 'loading' || total === 0}
            onClick={() => void selectAllFiltered()}
          >
            {bulkState === 'loading'
              ? 'Selecionando…'
              : debouncedSearch
                ? `Selecionar as ${total} filtradas`
                : `Selecionar todas (${total})`}
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={disabled || selectedIds.length === 0}
            onClick={() => update([], null)}
          >
            Limpar seleção
          </Button>
        </div>
      </div>
      {bulkState === 'too-many' && (
        <p role="alert" className="clinic-batch-picker__hint clinic-batch-picker__hint--error">
          Isso passaria de {MAX_CLINICS_PER_CHANGE} clínicas. Refine a busca e selecione por partes.
        </p>
      )}
      {bulkState === 'error' && (
        <p role="alert" className="clinic-batch-picker__hint clinic-batch-picker__hint--error">
          Não foi possível selecionar todas. Tente novamente.
        </p>
      )}

      <div className="clinic-batch-picker__list" role="group" aria-label="Clínicas disponíveis">
        {query.isLoading && <p className="clinic-batch-picker__hint">Carregando clínicas…</p>}
        {query.isError && (
          <p role="alert" className="clinic-batch-picker__hint clinic-batch-picker__hint--error">
            Não foi possível carregar as clínicas.
          </p>
        )}
        {!query.isLoading && !query.isError && pageItems?.length === 0 && (
          <p className="clinic-batch-picker__hint">Nenhuma clínica encontrada.</p>
        )}
        {pageItems?.map((clinic) => (
          <Checkbox
            key={clinic.id}
            label={clinic.name}
            disabled={disabled}
            checked={selected.has(clinic.id)}
            onChange={() => toggle(clinic.id)}
          />
        ))}
      </div>
      <Pagination
        itemLabel={['clínica', 'clínicas']}
        page={query.data?.page ?? page}
        pageSize={PAGE_SIZE}
        total={total}
        onPageChange={setPage}
      />

      <div className="clinic-batch-picker__selected">
        <p className="clinic-batch-picker__count" aria-live="polite">
          {selectedIds.length === 1
            ? '1 clínica selecionada'
            : `${selectedIds.length} clínicas selecionadas`}
        </p>
        {selectedIds.length > SELECTED_FILTER_THRESHOLD && (
          <TextField
            id={filterId}
            label="Filtrar selecionadas"
            value={selectedFilter}
            disabled={disabled}
            onChange={(event) => setSelectedFilter(event.target.value)}
          />
        )}
        {selectedIds.length > 0 && (
          <ul className="clinic-batch-picker__chips" aria-label="Clínicas selecionadas" tabIndex={0}>
            {visibleSelected.map((id) => (
              <li key={id} className="clinic-batch-picker__chip" data-primary={id === primaryId}>
                <span>
                  {nameOf(id)}
                  {id === primaryId ? ' · Principal' : ''}
                </span>
                <button
                  type="button"
                  aria-label={`Remover ${nameOf(id)}`}
                  disabled={disabled}
                  onClick={() => toggle(id)}
                >
                  <CloseIcon />
                </button>
              </li>
            ))}
          </ul>
        )}
        {selectedIds.length > 0 && (
          <Dropdown
            variant="field"
            label="Clínica principal"
            searchable
            options={selectedIds.map((id) => ({ value: id, label: nameOf(id) }))}
            value={primaryId ?? ''}
            disabled={disabled}
            onChange={(value) => update(selectedIds, value)}
          />
        )}
      </div>
    </div>
  )
}
