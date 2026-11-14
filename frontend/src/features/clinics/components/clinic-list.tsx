import { SearchIcon } from '../../../shared/ui/icons'
import { Pagination } from '../../../shared/ui/pagination'
import { formatTaxId, pluralize } from '../../../shared/lib/formatters'
import type { Clinic } from '../api/clinics-api'
import { ClinicStatusBadge } from './clinic-status-badge'
import './clinic-list.css'

interface ClinicListProps {
  clinics: Clinic[]
  activeCount: number
  selectedId: string | null
  search: string
  isLoading: boolean
  onSearchChange: (value: string) => void
  onSelect: (id: string) => void
  page?: number
  pageSize?: number
  total?: number
  onPageChange?: (page: number) => void
}

export function ClinicList({
  clinics,
  activeCount,
  selectedId,
  search,
  isLoading,
  onSearchChange,
  onSelect,
  page,
  pageSize,
  total,
  onPageChange,
}: ClinicListProps) {
  return (
    <div className="clinic-list">
      <div className="clinic-list__search">
        <SearchIcon className="clinic-list__search-icon" />
        <input
          type="search"
          className="clinic-list__search-input"
          placeholder="Buscar clínica..."
          aria-label="Buscar clínica"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
        <span className="clinic-list__count">
          {activeCount} {pluralize(activeCount, 'ativa', 'ativas')}
        </span>
      </div>

      <div className="clinic-list__rows">
        {isLoading && <p className="clinic-list__empty">Carregando…</p>}
        {!isLoading && clinics.length === 0 && (
          <p className="clinic-list__empty">Nenhuma clínica encontrada.</p>
        )}
        {clinics.map((clinic) => (
          <button
            key={clinic.id}
            type="button"
            className="clinic-list__row"
            data-selected={clinic.id === selectedId}
            onClick={() => onSelect(clinic.id)}
          >
            <div className="clinic-list__row-header">
              <span className="clinic-list__row-name">{clinic.name}</span>
              <ClinicStatusBadge status={clinic.status} />
            </div>
            {(clinic.addressStreet || clinic.addressCity) && (
              <div className="clinic-list__row-address">
                {[clinic.addressStreet, clinic.addressNumber].filter(Boolean).join(', ')}
                {clinic.addressCity ? ` — ${clinic.addressCity}/${clinic.addressState ?? ''}` : ''}
              </div>
            )}
            {(clinic.taxId || clinic.phone) && (
              <div className="clinic-list__row-meta">
                {[formatTaxId(clinic.taxId), clinic.phone].filter(Boolean).join(' · ')}
              </div>
            )}
          </button>
        ))}
      </div>
      {page && pageSize && total !== undefined && onPageChange && (
        <Pagination
          itemLabel={['clínica', 'clínicas']}
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={onPageChange}
        />
      )}
    </div>
  )
}
