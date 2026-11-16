import { Dropdown } from '../../../shared/ui/dropdown'
import { TextField } from '../../../shared/ui/text-field'
import { AGE_UNIT_LABELS, type PatientAgeUnit } from '../api/patients-api'
import './patient-age-field.css'

const UNIT_OPTIONS = (Object.keys(AGE_UNIT_LABELS) as PatientAgeUnit[]).map((unit) => ({
  value: unit,
  label: AGE_UNIT_LABELS[unit],
}))

interface PatientAgeFieldProps {
  idPrefix: string
  value: string
  unit: PatientAgeUnit
  disabled?: boolean
  errorMessage?: string
  onValueChange: (value: string) => void
  onUnitChange: (unit: PatientAgeUnit) => void
}

export function PatientAgeField({
  idPrefix,
  value,
  unit,
  disabled,
  errorMessage,
  onValueChange,
  onUnitChange,
}: PatientAgeFieldProps) {
  return (
    <div className="patient-age-field">
      <TextField
        id={`${idPrefix}-age`}
        label="Idade"
        inputMode="numeric"
        autoComplete="off"
        disabled={disabled}
        value={value}
        errorMessage={errorMessage}
        onChange={(event) => onValueChange(event.target.value)}
      />
      <Dropdown
        variant="field"
        label="Unidade"
        options={UNIT_OPTIONS}
        disabled={disabled}
        value={unit}
        onChange={(next) => onUnitChange(next as PatientAgeUnit)}
      />
    </div>
  )
}
