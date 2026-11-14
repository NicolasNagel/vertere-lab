import { useState } from 'react'

import { Dropdown, type DropdownOption } from '../../../shared/ui/dropdown'
import { CalendarIcon, ClinicsIcon, CloseIcon, TagIcon } from '../../../shared/ui/icons'
import { SERVICE_LEVEL_LABELS, type ServiceLevel } from '../api/attendances-api'
import './attendance-list-filters.css'

const SERVICE_LEVEL_FILTER_OPTIONS: DropdownOption[] = [
  { value: '', label: 'Todos' },
  { value: 'NORMAL', label: SERVICE_LEVEL_LABELS.NORMAL },
  { value: 'PLANTAO_NORMAL', label: SERVICE_LEVEL_LABELS.PLANTAO_NORMAL },
  { value: 'PLANTAO_ESPECIAL', label: SERVICE_LEVEL_LABELS.PLANTAO_ESPECIAL },
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
const PERIOD_OPTIONS: DropdownOption[] = Array.from({ length: 36 }, (_, index) => {
  const absoluteMonth = currentMonthIndex + 6 - index
  const year = Math.floor(absoluteMonth / 12)
  const monthIndex = ((absoluteMonth % 12) + 12) % 12
  const value = `${year}-${String(monthIndex + 1).padStart(2, '0')}`
  return { value, label: `${PERIOD_MONTH_LABELS[monthIndex]} ${year}` }
})

interface AttendanceListFiltersProps {
  clinicOptions: DropdownOption[]
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
      <Dropdown
        label="Competência"
        icon={<CalendarIcon />}
        options={[{ value: '', label: 'Todas' }, ...PERIOD_OPTIONS]}
        value={selectedPeriod}
        disabled={disabled}
        onChange={handlePeriodChange}
      />
      <Dropdown
        label="Clínica"
        icon={<ClinicsIcon />}
        className="attendance-list-filters__wide"
        options={[{ value: '', label: 'Todas' }, ...clinicOptions]}
        value={clinicId}
        disabled={disabled}
        searchable
        onChange={onClinicChange}
      />
      <Dropdown
        label="Tipo"
        icon={<TagIcon />}
        options={SERVICE_LEVEL_FILTER_OPTIONS}
        value={serviceLevel}
        disabled={disabled}
        onChange={(value) => onServiceLevelChange(value as ServiceLevel | '')}
      />
      {hasActiveFilters && (
        <button type="button" className="attendance-list-filters__clear" onClick={handleClear}>
          <CloseIcon /> Limpar filtros
        </button>
      )}
    </div>
  )
}
