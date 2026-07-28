import { SelectField, type SelectOption } from '../../../shared/ui/select'
import './closure-preview-filters.css'

const MONTH_OPTIONS: SelectOption[] = [
  { value: '1', label: 'Janeiro' },
  { value: '2', label: 'Fevereiro' },
  { value: '3', label: 'Março' },
  { value: '4', label: 'Abril' },
  { value: '5', label: 'Maio' },
  { value: '6', label: 'Junho' },
  { value: '7', label: 'Julho' },
  { value: '8', label: 'Agosto' },
  { value: '9', label: 'Setembro' },
  { value: '10', label: 'Outubro' },
  { value: '11', label: 'Novembro' },
  { value: '12', label: 'Dezembro' },
]

function yearOptions(): SelectOption[] {
  const currentYear = new Date().getFullYear()
  const years = [currentYear - 1, currentYear, currentYear + 1]
  return years.map((year) => ({ value: String(year), label: String(year) }))
}

interface ClosurePreviewFiltersProps {
  clinicOptions: SelectOption[]
  clinicId: string
  year: number
  month: number
  onClinicChange: (clinicId: string) => void
  onYearChange: (year: number) => void
  onMonthChange: (month: number) => void
}

export function ClosurePreviewFilters({
  clinicOptions,
  clinicId,
  year,
  month,
  onClinicChange,
  onYearChange,
  onMonthChange,
}: ClosurePreviewFiltersProps) {
  return (
    <div className="closure-preview-filters">
      <SelectField
        label="Clínica"
        id="closure-preview-clinic"
        className="closure-preview-filters__field"
        options={[{ value: '', label: 'Selecione uma clínica' }, ...clinicOptions]}
        value={clinicId}
        onChange={(event) => onClinicChange(event.target.value)}
      />
      <SelectField
        label="Mês"
        id="closure-preview-month"
        className="closure-preview-filters__field closure-preview-filters__field--small"
        options={MONTH_OPTIONS}
        value={String(month)}
        onChange={(event) => onMonthChange(Number(event.target.value))}
      />
      <SelectField
        label="Ano"
        id="closure-preview-year"
        className="closure-preview-filters__field closure-preview-filters__field--small"
        options={yearOptions()}
        value={String(year)}
        onChange={(event) => onYearChange(Number(event.target.value))}
      />
    </div>
  )
}
