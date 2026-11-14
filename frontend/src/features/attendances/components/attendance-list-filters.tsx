import { useState } from 'react'

import { SelectField, type SelectOption } from '../../../shared/ui/select'
import { CalendarIcon, ClinicsIcon, CloseIcon, TagIcon } from '../../../shared/ui/icons'
import { SERVICE_LEVEL_LABELS, type ServiceLevel } from '../api/attendances-api'
import './attendance-list-filters.css'

const SERVICE_LEVEL_FILTER_OPTIONS: SelectOption[] = [
  { value: '', label: 'Tipo: Todos' },
  { value: 'NORMAL', label: `Tipo: ${SERVICE_LEVEL_LABELS.NORMAL}` },
  { value: 'PLANTAO_NORMAL', label: `Tipo: ${SERVICE_LEVEL_LABELS.PLANTAO_NORMAL}` },
  { value: 'PLANTAO_ESPECIAL', label: `Tipo: ${SERVICE_LEVEL_LABELS.PLANTAO_ESPECIAL}` },
]

const PERIOD_MONTH_LABELS = [
  'Jan',
  'Fev',
  'Mar',
  'Abr',
  'Mai',
  'Jun',
  'Jul',
  'Ago',
  'Set',
  'Out',
  'Nov',
  'Dez',
]
const currentMonth = new Date()
const currentMonthIndex = currentMonth.getFullYear() * 12 + currentMonth.getMonth()
const PERIOD_OPTIONS: SelectOption[] = Array.from({ length: 36 }, (_, index) => {
  const absoluteMonth = currentMonthIndex + 6 - index
  const year = Math.floor(absoluteMonth / 12)
  const monthIndex = ((absoluteMonth % 12) + 12) % 12
  const value = `${year}-${String(monthIndex + 1).padStart(2, '0')}`
  return { value, label: `${PERIOD_MONTH_LABELS[monthIndex]} ${year}` }
})

interface AttendanceListFiltersProps {
  clinicOptions: SelectOption[]
  clinicId: string
  serviceLevel: ServiceLevel | ''
  disabled: boolean
  onClinicChange: (clinicId: string) => void
  onServiceLevelChange: (serviceLevel: ServiceLevel | '') => void
  onServiceDateFromChange: (value: string) => void
  onServiceDateToChange: (value: string) => void
}

export function AttendanceListFilters({
  clinicOptions,
  clinicId,
  serviceLevel,
  disabled,
  onClinicChange,
  onServiceLevelChange,
  onServiceDateFromChange,
  onServiceDateToChange,
}: AttendanceListFiltersProps) {
  const [selectedPeriod, setSelectedPeriod] = useState('')

  function handlePeriodChange(period: string) {
    setSelectedPeriod(period)
    if (!period) {
      onServiceDateFromChange('')
      onServiceDateToChange('')
      return
    }
    const [year, month] = period.split('-')
    if (!year || !month) return
    const lastDay = new Date(Date.UTC(Number(year), Number(month), 0)).getUTCDate()
    onServiceDateFromChange(`${period}-01`)
    onServiceDateToChange(`${period}-${String(lastDay).padStart(2, '0')}`)
  }

  const hasActiveFilters = selectedPeriod !== '' || clinicId !== '' || serviceLevel !== ''

  function handleClear() {
    handlePeriodChange('')
    onClinicChange('')
    onServiceLevelChange('')
  }

  return (
    <div className="attendance-list-filters" role="group" aria-label="Filtros">
      <SelectField
        label="Competência"
        id="attendance-list-period"
        className="attendance-list-filters__field"
        leadingIcon={<CalendarIcon />}
        options={[{ value: '', label: 'Período: Todos' }, ...PERIOD_OPTIONS]}
        value={selectedPeriod}
        disabled={disabled}
        onChange={(event) => handlePeriodChange(event.target.value)}
      />
      <SelectField
        label="Clínica"
        id="attendance-list-clinic"
        className="attendance-list-filters__field attendance-list-filters__field--wide"
        leadingIcon={<ClinicsIcon />}
        options={[{ value: '', label: 'Clínica: Todas' }, ...clinicOptions]}
        value={clinicId}
        disabled={disabled}
        onChange={(event) => onClinicChange(event.target.value)}
      />
      <SelectField
        label="Tipo"
        id="attendance-list-service-level"
        className="attendance-list-filters__field"
        leadingIcon={<TagIcon />}
        options={SERVICE_LEVEL_FILTER_OPTIONS}
        value={serviceLevel}
        disabled={disabled}
        onChange={(event) => onServiceLevelChange(event.target.value as ServiceLevel | '')}
      />
      {hasActiveFilters && (
        <button type="button" className="attendance-list-filters__clear" onClick={handleClear}>
          <CloseIcon /> Limpar filtros
        </button>
      )}
    </div>
  )
}
