import { SearchIcon } from '../../../shared/ui/icons'
import { Pagination } from '../../../shared/ui/pagination'
import { formatTaxId, pluralize } from '../../../shared/lib/formatters'
import type { Clinic, ClinicStatus } from '../api/clinics-api'
import { ClinicStatusBadge } from './clinic-status-badge'
import './clinic-table.css'

const STATUS_FILTERS: { value: ClinicStatus | undefined; label: string }[] = [
  { value: undefined, label: 'Todas' },
  { value: 'ACTIVE', label: 'Ativas' },
  { value: 'SPECIAL', label: 'Especiais' },
  { value: 'DELINQUENT', label: 'Negativadas' },
  { value: 'INACTIVE', label: 'Inativas' },
]

interface ClinicTableProps {
  clinics: Clinic[]
  activeCount: number
  selectedId: string | null
  search: string
  status: ClinicStatus | undefined
  isLoading: boolean
  isError: boolean
  page: number
  pageSize: number
  total: number
  onSearchChange: (value: string) => void
  onStatusChange: (status: ClinicStatus | undefined) => void
  onSelect: (id: string) => void
  onPageChange: (page: number) => void
}

export function ClinicTable({
  clinics,
  activeCount,
  selectedId,
  search,
  status,
  isLoading,
  isError,
  page,
  pageSize,
  total,
  onSearchChange,
  onStatusChange,
  onSelect,
  onPageChange,
}: ClinicTableProps) {
  return (
    <div className="clinic-table">
      <div className="clinic-table__toolbar">
        <label className="clinic-table__search">
          <SearchIcon />
          <input
            type="search"
            placeholder="Buscar por nome, CNPJ ou cidade…"
            aria-label="Buscar clínica"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </label>
        <div className="clinic-table__filters" role="group" aria-label="Filtrar por status">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.label}
              type="button"
              className="clinic-table__filter"
              aria-pressed={filter.value === status}
              onClick={() => onStatusChange(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <span className="clinic-table__count">
          {activeCount} {pluralize(activeCount, 'ativa', 'ativas')}
        </span>
      </div>

      <div className="clinic-table__scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Clínica</th>
              <th scope="col" className="clinic-table__optional">
                CNPJ
              </th>
              <th scope="col">Cidade / UF</th>
              <th scope="col" className="clinic-table__optional">
                Telefone
              </th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {clinics.map((clinic) => (
              <tr key={clinic.id} data-selected={clinic.id === selectedId}>
                <td className="clinic-table__name">
                  <button type="button" onClick={() => onSelect(clinic.id)}>
                    {clinic.name}
                  </button>
                </td>
                <td className="clinic-table__mono clinic-table__optional">
                  {formatTaxId(clinic.taxId) ?? '—'}
                </td>
                <td>
                  {clinic.addressCity
                    ? `${clinic.addressCity} / ${clinic.addressState ?? '—'}`
                    : '—'}
                </td>
                <td className="clinic-table__mono clinic-table__optional">{clinic.phone ?? '—'}</td>
                <td>
                  <ClinicStatusBadge status={clinic.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {isLoading && <p className="clinic-table__empty">Carregando…</p>}
        {isError && <p className="clinic-table__empty">Não foi possível carregar as clínicas.</p>}
        {!isLoading && !isError && clinics.length === 0 && (
          <p className="clinic-table__empty">Nenhuma clínica encontrada.</p>
        )}
      </div>

      <Pagination
        itemLabel={['clínica', 'clínicas']}
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={onPageChange}
      />
    </div>
  )
}
