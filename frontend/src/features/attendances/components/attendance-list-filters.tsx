import { SelectField, type SelectOption } from '../../../shared/ui/select'
import type { AttendanceStatus } from '../api/attendances-api'
import './attendance-list-filters.css'

const STATUS_OPTIONS: SelectOption[] = [
  { value: '', label: 'Todos os status' },
  { value: 'DRAFT', label: 'Rascunho' },
  { value: 'CONFIRMED', label: 'Confirmado' },
  { value: 'IN_PROGRESS', label: 'Em andamento' },
  { value: 'COMPLETED', label: 'Concluído' },
  { value: 'CANCELLED', label: 'Cancelado' },
  { value: 'ON_HOLD', label: 'Em espera' },
]

interface AttendanceListFiltersProps {
  clinicOptions: SelectOption[]
  veterinarianOptions: SelectOption[]
  clinicId: string
  veterinarianId: string
  status: AttendanceStatus | ''
  protocolNumber: string
  ownerName: string
  serviceDateFrom: string
  serviceDateTo: string
  disabled: boolean
  onClinicChange: (clinicId: string) => void
  onVeterinarianChange: (veterinarianId: string) => void
  onStatusChange: (status: AttendanceStatus | '') => void
  onProtocolNumberChange: (value: string) => void
  onOwnerNameChange: (value: string) => void
  onServiceDateFromChange: (value: string) => void
  onServiceDateToChange: (value: string) => void
}

export function AttendanceListFilters({
  clinicOptions,
  veterinarianOptions,
  clinicId,
  veterinarianId,
  status,
  protocolNumber,
  ownerName,
  serviceDateFrom,
  serviceDateTo,
  disabled,
  onClinicChange,
  onVeterinarianChange,
  onStatusChange,
  onProtocolNumberChange,
  onOwnerNameChange,
  onServiceDateFromChange,
  onServiceDateToChange,
}: AttendanceListFiltersProps) {
  return (
    <div className="attendance-list-filters">
      <SelectField
        label="Status"
        id="attendance-list-status"
        className="attendance-list-filters__field"
        options={STATUS_OPTIONS}
        value={status}
        disabled={disabled}
        onChange={(event) => onStatusChange(event.target.value as AttendanceStatus | '')}
      />
      <label className="attendance-list-filters__field">
        <span>Protocolo</span>
        <input
          value={protocolNumber}
          maxLength={32}
          disabled={disabled}
          placeholder="2026/000001"
          onChange={(event) => onProtocolNumberChange(event.target.value)}
        />
      </label>
      <label className="attendance-list-filters__field">
        <span>Tutor</span>
        <input
          value={ownerName}
          maxLength={200}
          disabled={disabled}
          onChange={(event) => onOwnerNameChange(event.target.value)}
        />
      </label>
      <label className="attendance-list-filters__field">
        <span>Data inicial</span>
        <input
          type="date"
          value={serviceDateFrom}
          disabled={disabled}
          onChange={(event) => onServiceDateFromChange(event.target.value)}
        />
      </label>
      <label className="attendance-list-filters__field">
        <span>Data final</span>
        <input
          type="date"
          value={serviceDateTo}
          min={serviceDateFrom || undefined}
          disabled={disabled}
          onChange={(event) => onServiceDateToChange(event.target.value)}
        />
      </label>
      <SelectField
        label="Clínica"
        id="attendance-list-clinic"
        className="attendance-list-filters__field"
        options={[{ value: '', label: 'Todas as clínicas' }, ...clinicOptions]}
        value={clinicId}
        disabled={disabled}
        onChange={(event) => onClinicChange(event.target.value)}
      />
      <SelectField
        label="Veterinário"
        id="attendance-list-veterinarian"
        className="attendance-list-filters__field"
        options={[{ value: '', label: 'Todos os veterinários' }, ...veterinarianOptions]}
        value={veterinarianId}
        disabled={disabled}
        onChange={(event) => onVeterinarianChange(event.target.value)}
      />
    </div>
  )
}
