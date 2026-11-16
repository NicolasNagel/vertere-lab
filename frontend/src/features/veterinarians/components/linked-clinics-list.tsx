import { useState } from 'react'

import { TextField } from '../../../shared/ui/text-field'
import type { VeterinarianLinkedClinic } from '../api/veterinarians-api'
import './clinic-batch-picker.css'

const FILTER_THRESHOLD = 8

function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

/** Clínicas vinculadas em leitura: altura limitada com rolagem e busca quando a lista é longa. */
export function LinkedClinicsList({
  veterinarianId,
  clinics,
}: {
  veterinarianId: string
  clinics: VeterinarianLinkedClinic[]
}) {
  const [filter, setFilter] = useState('')
  const term = normalize(filter.trim())
  const visible = term
    ? clinics.filter((clinic) => normalize(clinic.clinicName).includes(term))
    : clinics

  return (
    <div className="clinic-batch-picker__selected">
      {clinics.length > FILTER_THRESHOLD && (
        <TextField
          id={`veterinarian-linked-filter-${veterinarianId}`}
          label="Buscar nas clínicas vinculadas"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
      )}
      {clinics.length > FILTER_THRESHOLD && (
        <p className="clinic-batch-picker__count" aria-live="polite">
          {visible.length} de {clinics.length} clínicas
        </p>
      )}
      <ul
        className="clinic-batch-picker__chips clinic-batch-picker__chips--read"
        aria-label="Clínicas vinculadas"
        tabIndex={0}
      >
        {visible.map((clinic) => (
          <li
            key={clinic.clinicId}
            className="clinic-batch-picker__chip clinic-batch-picker__chip--read"
            data-primary={clinic.primaryClinic}
          >
            <span>
              {clinic.clinicName}
              {clinic.primaryClinic ? ' · Principal' : ''}
            </span>
          </li>
        ))}
        {visible.length === 0 && (
          <li className="clinic-batch-picker__hint">Nenhuma clínica encontrada.</li>
        )}
      </ul>
    </div>
  )
}
