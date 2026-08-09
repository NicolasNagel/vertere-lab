import { useState } from 'react'

import { useCreatePatientMutation } from '../../patients/api/use-create-patient-mutation'
import type { Patient } from '../../patients/api/patients-api'
import { AttendancePatientForm } from './attendance-patient-form'
import { PatientPicker } from './patient-picker'
import './attendance-patient-section.css'

interface AttendancePatientSectionProps {
  clinicId: string
  selectedPatient: Patient | null
  disabled?: boolean
  onSelect: (patient: Patient) => void
  onClear: () => void
}

/** Cadastro inline é a ação principal (Tela 4 do mockup mostra o
 * formulário de paciente direto na tela, não uma busca) — buscar um
 * paciente já existente é a ação secundária, atrás do link "buscar do
 * histórico". O botão "Cancelar" do formulário de cadastro volta para o
 * modo de busca, que é o equivalente inline de "desistir de cadastrar". */
export function AttendancePatientSection({
  clinicId,
  selectedPatient,
  disabled,
  onSelect,
  onClear,
}: AttendancePatientSectionProps) {
  const [mode, setMode] = useState<'create' | 'search'>('create')
  const createMutation = useCreatePatientMutation()

  if (selectedPatient) {
    return (
      <PatientPicker
        selectedPatient={selectedPatient}
        disabled={disabled}
        canCreate={false}
        onSelect={onSelect}
        onClear={onClear}
        onRequestCreate={() => undefined}
      />
    )
  }

  return (
    <div className="attendance-patient-section">
      <div className="attendance-patient-section__header">
        <button
          type="button"
          className="attendance-patient-section__mode-link"
          disabled={disabled}
          onClick={() => setMode(mode === 'create' ? 'search' : 'create')}
        >
          {mode === 'create' ? '+ buscar do histórico' : '+ cadastrar novo paciente'}
        </button>
      </div>

      {mode === 'create' ? (
        <AttendancePatientForm
          clinicId={clinicId}
          submitting={createMutation.isPending || Boolean(disabled)}
          error={createMutation.error}
          onCancel={() => setMode('search')}
          onSubmitCreate={(values) => createMutation.mutate(values, { onSuccess: onSelect })}
        />
      ) : (
        <PatientPicker
          selectedPatient={null}
          disabled={disabled}
          canCreate={false}
          onSelect={onSelect}
          onClear={onClear}
          onRequestCreate={() => setMode('create')}
        />
      )}
    </div>
  )
}
