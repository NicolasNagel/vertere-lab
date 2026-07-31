import { SearchIcon } from '../../../shared/ui/icons'
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

      <div className="veterinarian-list__filters" role="group" aria-label="Filtrar por tipo">
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

      <div className="veterinarian-list__rows" role="list">
        {isLoading && <p className="veterinarian-list__empty">Carregando…</p>}
        {!isLoading && veterinarians.length === 0 && (
          <p className="veterinarian-list__empty">Nenhum veterinário encontrado.</p>
        )}
        {veterinarians.map((veterinarian) => (
          <button
            key={veterinarian.id}
            type="button"
            role="listitem"
            className="veterinarian-list__row"
            data-selected={veterinarian.id === selectedId}
            onClick={() => onSelect(veterinarian.id)}
          >
            <div className="veterinarian-list__row-header">
              <span className="veterinarian-list__row-name">{veterinarian.name}</span>
              <span className="veterinarian-list__row-badges">
                {veterinarian.isAutonomous && (
                  <span className="veterinarian-list__row-autonomous">Autônomo</span>
                )}
                <span className="veterinarian-list__row-status" data-status={veterinarian.status}>
                  {STATUS_LABELS[veterinarian.status]}
                </span>
              </span>
            </div>
            <div className="veterinarian-list__row-crmv">{veterinarian.crmv}</div>
            {(veterinarian.phone || veterinarian.email) && (
              <div className="veterinarian-list__row-meta">
                {[veterinarian.phone, veterinarian.email].filter(Boolean).join(' · ')}
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
