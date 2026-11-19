import { SearchIcon } from '../../../shared/ui/icons'
import { Pagination } from '../../../shared/ui/pagination'
import { pluralize } from '../../../shared/lib/formatters'
import type { Patient } from '../api/patients-api'
import './patient-list.css'

const STATUS_LABELS: Record<Patient['status'], string> = {
  ACTIVE: 'Ativo',
  INACTIVE: 'Inativo',
}

interface PatientListProps {
  patients: Patient[]
  activeCount: number
  selectedId: string | null
  search: string
  isLoading: boolean
  isError?: boolean
  onSearchChange: (value: string) => void
  onSelect: (id: string) => void
  page?: number
  pageSize?: number
  total?: number
  onPageChange?: (page: number) => void
}

export function PatientList({
  patients,
  activeCount,
  selectedId,
  search,
  isLoading,
  isError = false,
  onSearchChange,
  onSelect,
  page,
  pageSize,
  total,
  onPageChange,
}: PatientListProps) {
  return (
    <div className="patient-list">
      <div className="patient-list__search">
        <SearchIcon className="patient-list__search-icon" />
        <input
          type="search"
          className="patient-list__search-input"
          placeholder="Buscar por nome ou tutor..."
          aria-label="Buscar paciente"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
        <span className="patient-list__count">
          {activeCount} {pluralize(activeCount, 'ativo', 'ativos')}
        </span>
      </div>

      <div className="patient-list__rows">
        {isLoading && <p className="patient-list__empty">Carregando…</p>}
        {isError && (
          <p role="alert" className="patient-list__empty">
            Não foi possível carregar os pacientes.
          </p>
        )}
        {!isLoading && !isError && patients.length === 0 && (
          <p className="patient-list__empty">Nenhum paciente encontrado.</p>
        )}
        {patients.map((patient) => (
          <button
            key={patient.id}
            type="button"
            className="patient-list__row"
            data-selected={patient.id === selectedId}
            onClick={() => onSelect(patient.id)}
          >
            <div className="patient-list__row-header">
              <span className="patient-list__row-name">{patient.name}</span>
              <span className="patient-list__row-status" data-status={patient.status}>
                {STATUS_LABELS[patient.status]}
              </span>
            </div>
            <div className="patient-list__row-owner">{patient.ownerName}</div>
          </button>
        ))}
      </div>
      {page && pageSize && total !== undefined && onPageChange && (
        <Pagination
          itemLabel={['paciente', 'pacientes']}
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={onPageChange}
        />
      )}
    </div>
  )
}
