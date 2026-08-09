import { SelectField, type SelectOption } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import './closure-preview-filters.css'

interface ClosurePreviewFiltersProps {
  clinicOptions: SelectOption[]
  clinicId: string
  periodStart: string
  periodEnd: string
  onClinicChange: (clinicId: string) => void
  onPeriodStartChange: (periodStart: string) => void
  onPeriodEndChange: (periodEnd: string) => void
}

/** Período livre (não só mês calendário) — algumas clínicas fecham
 * quinzenalmente, então o operador escolhe início/fim diretamente
 * (`.claude/rules/13-monthly-closure.md`). */
export function ClosurePreviewFilters({
  clinicOptions,
  clinicId,
  periodStart,
  periodEnd,
  onClinicChange,
  onPeriodStartChange,
  onPeriodEndChange,
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
      <TextField
        label="De"
        id="closure-preview-period-start"
        className="closure-preview-filters__field closure-preview-filters__field--small"
        type="date"
        value={periodStart}
        max={periodEnd || undefined}
        onChange={(event) => onPeriodStartChange(event.target.value)}
      />
      <TextField
        label="Até"
        id="closure-preview-period-end"
        className="closure-preview-filters__field closure-preview-filters__field--small"
        type="date"
        value={periodEnd}
        min={periodStart || undefined}
        onChange={(event) => onPeriodEndChange(event.target.value)}
      />
    </div>
  )
}
