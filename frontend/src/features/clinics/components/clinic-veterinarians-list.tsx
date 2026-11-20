import { useId, useState } from 'react'

import { getInitials, normalizeSearchText } from '../../../shared/lib/formatters'
import { Button } from '../../../shared/ui/button'
import { TextField } from '../../../shared/ui/text-field'
import type { ClinicLinkedVeterinarian } from '../api/clinics-api'
import './clinic-detail.css'

/** Quantos veterinários aparecem antes de "Ver todos": o popover continua curto com 20 vínculos. */
const PREVIEW_COUNT = 5

function VeterinarianRow({ veterinarian }: { veterinarian: ClinicLinkedVeterinarian }) {
  return (
    <li className="clinic-detail__vets-row">
      <span className="clinic-detail__vets-avatar" aria-hidden="true">
        {getInitials(veterinarian.veterinarianName)}
      </span>
      <span className="clinic-detail__vets-info">
        <span className="clinic-detail__vets-name">
          {veterinarian.veterinarianName}
          {veterinarian.primaryClinic && <span className="clinic-detail__vets-primary">Principal</span>}
        </span>
        <span className="clinic-detail__vets-crmv clinic-detail__mono">{veterinarian.crmv}</span>
      </span>
    </li>
  )
}

/**
 * Veterinários vinculados à clínica. Até 5 aparecem direto; acima disso, uma prévia de 5 e o botão
 * "Ver todos (N)", que abre uma busca e uma lista com altura limitada (rola dentro do popover).
 */
export function ClinicVeterinariansList({
  veterinarians,
}: {
  veterinarians: ClinicLinkedVeterinarian[]
}) {
  const [expanded, setExpanded] = useState(false)
  const [filter, setFilter] = useState('')
  const panelId = useId()

  if (veterinarians.length === 0) {
    return <p className="clinic-detail__empty">Nenhum veterinário vinculado ainda.</p>
  }

  const isLong = veterinarians.length > PREVIEW_COUNT
  if (!isLong) {
    return (
      <ul className="clinic-detail__vets-list">
        {veterinarians.map((veterinarian) => (
          <VeterinarianRow key={veterinarian.veterinarianId} veterinarian={veterinarian} />
        ))}
      </ul>
    )
  }

  if (!expanded) {
    return (
      <>
        <ul className="clinic-detail__vets-list">
          {veterinarians.slice(0, PREVIEW_COUNT).map((veterinarian) => (
            <VeterinarianRow key={veterinarian.veterinarianId} veterinarian={veterinarian} />
          ))}
        </ul>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="clinic-detail__vets-toggle"
          onClick={() => setExpanded(true)}
        >
          Ver todos ({veterinarians.length})
        </Button>
      </>
    )
  }

  const term = normalizeSearchText(filter.trim())
  const visible = term
    ? veterinarians.filter(
        (veterinarian) =>
          normalizeSearchText(veterinarian.veterinarianName).includes(term) ||
          normalizeSearchText(veterinarian.crmv).includes(term),
      )
    : veterinarians

  return (
    <div id={panelId} className="clinic-detail__vets-expanded">
      <TextField
        id={`${panelId}-search`}
        label="Buscar veterinário vinculado"
        placeholder="Nome ou CRMV"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
      />
      <p className="clinic-detail__vets-count" aria-live="polite">
        {visible.length} de {veterinarians.length} veterinários
      </p>
      <ul
        className="clinic-detail__vets-list clinic-detail__vets-list--bounded"
        aria-label="Veterinários vinculados"
        tabIndex={0}
      >
        {visible.map((veterinarian) => (
          <VeterinarianRow key={veterinarian.veterinarianId} veterinarian={veterinarian} />
        ))}
        {visible.length === 0 && <li className="clinic-detail__empty">Nenhum veterinário encontrado.</li>}
      </ul>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="clinic-detail__vets-toggle"
        onClick={() => {
          setExpanded(false)
          setFilter('')
        }}
      >
        Mostrar menos
      </Button>
    </div>
  )
}
