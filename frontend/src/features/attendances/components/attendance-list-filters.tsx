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
  disabled: boolean
  onClinicChange: (clinicId: string) => void
  onVeterinarianChange: (veterinarianId: string) => void
  onStatusChange: (status: AttendanceStatus | '') => void
}

export function AttendanceListFilters({
  clinicOptions,
  veterinarianOptions,
  clinicId,
  veterinarianId,
  status,
  disabled,
  onClinicChange,
  onVeterinarianChange,
  onStatusChange,
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
