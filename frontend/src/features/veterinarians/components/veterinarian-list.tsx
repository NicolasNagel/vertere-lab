import { SearchIcon } from '../../../shared/ui/icons'
import { Pagination } from '../../../shared/ui/pagination'
import { pluralize } from '../../../shared/lib/formatters'
import type { Veterinarian } from '../api/veterinarians-api'
import './veterinarian-list.css'

const STATUS_LABELS: Record<Veterinarian['status'], string> = {
  ACTIVE: 'Ativo',
  INACTIVE: 'Inativo',
}

export type VeterinarianTypeFilter = 'all' | 'linked' | 'autonomous'

const TYPE_FILTERS: { value: VeterinarianTypeFilter; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'linked', label: 'Vinculados' },
  { value: 'autonomous', label: 'Autônomos' },
]

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  return `${parts[0]?.[0] ?? ''}${parts.at(-1)?.[0] ?? ''}`.toUpperCase()
}

interface VeterinarianListProps {
  veterinarians: Veterinarian[]
  activeCount: number
  selectedId: string | null
  search: string
  typeFilter: VeterinarianTypeFilter
  isLoading: boolean
  onSearchChange: (value: string) => void
  onTypeFilterChange: (value: VeterinarianTypeFilter) => void
  onSelect: (id: string) => void
  page?: number
  pageSize?: number
  total?: number
  onPageChange?: (page: number) => void
}

export function VeterinarianList({
  veterinarians,
  activeCount,
  selectedId,
  search,
  typeFilter,
  isLoading,
  onSearchChange,
  onTypeFilterChange,
  onSelect,
  page,
  pageSize,
  total,
  onPageChange,
}: VeterinarianListProps) {
  return (
    <div className="veterinarian-list">
      <div className="veterinarian-list__search">
        <SearchIcon className="veterinarian-list__search-icon" />
        <input
          type="search"
          className="veterinarian-list__search-input"
          placeholder="Buscar por nome ou CRMV..."
          aria-label="Buscar veterinário"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
        <span className="veterinarian-list__count">
          {activeCount} {pluralize(activeCount, 'ativo', 'ativos')}
        </span>
      </div>

      <div className="veterinarian-list__filters" role="group" aria-label="Filtrar por tipo" hidden>
        {TYPE_FILTERS.map((filter) => (
          <button
            key={filter.value}
            type="button"
            className="veterinarian-list__filter"
            data-active={filter.value === typeFilter}
            onClick={() => onTypeFilterChange(filter.value)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <div className="veterinarian-list__rows">
        {isLoading && <p className="veterinarian-list__empty">Carregando…</p>}
        {!isLoading && veterinarians.length === 0 && (
          <p className="veterinarian-list__empty">Nenhum veterinário encontrado.</p>
        )}
        {veterinarians.map((veterinarian) => (
          <button
            key={veterinarian.id}
            type="button"
            className="veterinarian-list__row"
            data-selected={veterinarian.id === selectedId}
            onClick={() => onSelect(veterinarian.id)}
          >
            <div className="veterinarian-list__row-header">
              <span className="veterinarian-list__identity">
                <span className="veterinarian-list__avatar" aria-hidden="true">
                  {initials(veterinarian.name)}
                </span>
                <span>
                  <span className="veterinarian-list__row-name">{veterinarian.name}</span>
                  <span className="veterinarian-list__row-crmv">{veterinarian.crmv}</span>
                </span>
              </span>
              <span className="veterinarian-list__row-badges">
                {veterinarian.isAutonomous && (
                  <span className="veterinarian-list__row-autonomous">Autônomo</span>
                )}
                <span className="veterinarian-list__row-status" data-status={veterinarian.status}>
                  {STATUS_LABELS[veterinarian.status]}
                </span>
              </span>
            </div>
            {(veterinarian.phone || veterinarian.email) && (
              <div className="veterinarian-list__row-meta">
                {[veterinarian.phone, veterinarian.email].filter(Boolean).join(' · ')}
              </div>
            )}
          </button>
        ))}
      </div>
      {page && pageSize && total !== undefined && onPageChange && (
        <Pagination
          itemLabel={['veterinário', 'veterinários']}
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={onPageChange}
        />
      )}
    </div>
  )
}
