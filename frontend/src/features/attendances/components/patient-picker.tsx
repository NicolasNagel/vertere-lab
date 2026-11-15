import { useState } from 'react'

import { useDebouncedValue } from '../../../shared/lib/use-debounced-value'
import { Button } from '../../../shared/ui/button'
import { SearchIcon } from '../../../shared/ui/icons'
import { TextField } from '../../../shared/ui/text-field'
import { usePatientsQuery } from '../../patients/api/use-patients-query'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import type { Patient } from '../../patients/api/patients-api'
import './patient-picker.css'

interface PatientPickerProps {
  selectedPatient: Patient | null
  disabled?: boolean
  canCreate: boolean
  onSelect: (patient: Patient) => void
  onClear: () => void
  onRequestCreate: (searchTerm: string) => void
}

export function PatientPicker({
  selectedPatient,
  disabled,
  canCreate,
  onSelect,
  onClear,
  onRequestCreate,
}: PatientPickerProps) {
  const [query, setQuery] = useState('')
  const speciesQuery = useSpeciesQuery()
  const [page, setPage] = useState(1)
  const debouncedQuery = useDebouncedValue(query, 300)

  const searchQuery = usePatientsQuery(
    !selectedPatient && debouncedQuery.trim()
      ? { search: debouncedQuery.trim(), status: 'ACTIVE', page, pageSize: 10 }
      : null,
  )

  if (selectedPatient) {
    return (
      <div className="patient-picker">
        <span className="patient-picker__label">Paciente</span>
        <div className="patient-picker__selected">
          <div>
            <div className="patient-picker__selected-name">{selectedPatient.name}</div>
            <div className="patient-picker__selected-owner">
              {[
                speciesQuery.data?.find((species) => species.id === selectedPatient.speciesId)?.name,
                selectedPatient.sex === 'MALE' ? 'Macho' : 'Fêmea',
                selectedPatient.breed,
                selectedPatient.ageDescription,
              ]
                .filter(Boolean)
                .join(' · ')}
            </div>
            <div className="patient-picker__selected-owner">Tutor: {selectedPatient.ownerName}</div>
          </div>
          <Button type="button" variant="secondary" size="sm" disabled={disabled} onClick={onClear}>
            Trocar
          </Button>
        </div>
      </div>
    )
  }

  const results = query.trim() ? (searchQuery.data?.items ?? []) : []
  const showDuplicateHint =
    query.trim().length > 0 &&
    results.some((patient) => patient.name.toLowerCase().includes(query.trim().toLowerCase()))

  return (
    <div className="patient-picker">
      <TextField
        id="attendance-draft-patient-search"
        label="Paciente"
        icon={<SearchIcon />}
        placeholder="Buscar por nome ou tutor…"
        autoComplete="off"
        disabled={disabled}
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setPage(1)
        }}
      />

      {query.trim() && (
        <div className="patient-picker__results" role="listbox" aria-label="Resultados da busca">
          {searchQuery.isLoading && <p className="patient-picker__hint">Buscando…</p>}

          {searchQuery.isError && (
            <p role="alert" className="patient-picker__hint">
              Não foi possível buscar pacientes.
            </p>
          )}

          {!searchQuery.isLoading && results.length === 0 && (
            <p className="patient-picker__hint">Nenhum paciente encontrado.</p>
          )}

          {results.map((patient) => (
            <button
              key={patient.id}
              type="button"
              role="option"
              aria-selected={false}
              className="patient-picker__result"
              onClick={() => {
                onSelect(patient)
                setQuery('')
              }}
            >
              <span className="patient-picker__result-name">{patient.name}</span>
              <span className="patient-picker__result-owner">{patient.ownerName}</span>
            </button>
          ))}

          {searchQuery.data && searchQuery.data.total > searchQuery.data.pageSize && (
            <div className="patient-picker__pagination">
              <button
                type="button"
                disabled={page === 1 || searchQuery.isFetching}
                onClick={() => setPage((current) => current - 1)}
              >
                Anterior
              </button>
              <span>
                Página {page} de {Math.ceil(searchQuery.data.total / searchQuery.data.pageSize)}
              </span>
              <button
                type="button"
                disabled={
                  page >= Math.ceil(searchQuery.data.total / searchQuery.data.pageSize) ||
                  searchQuery.isFetching
                }
                onClick={() => setPage((current) => current + 1)}
              >
                Próxima
              </button>
            </div>
          )}

          {canCreate && (
            <div className="patient-picker__create">
              {showDuplicateHint && (
                <p className="patient-picker__duplicate-hint">
                  Já existe paciente com nome parecido acima — confirme que não é o mesmo antes de
                  criar um novo.
                </p>
              )}
              <button
                type="button"
                className="patient-picker__create-button"
                onClick={() => onRequestCreate(query.trim())}
              >
                + Cadastrar “{query.trim()}” como novo paciente
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
