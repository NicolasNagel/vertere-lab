import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { useDebouncedValue } from '../../../shared/lib/use-debounced-value'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { Dropdown, type DropdownOption } from '../../../shared/ui/dropdown'
import {
  ClinicsIcon,
  CloseIcon,
  PatientsIcon,
  PlusIcon,
  SearchIcon,
} from '../../../shared/ui/icons'
import { Modal } from '../../../shared/ui/modal'
import { PageHeader } from '../../../shared/ui/page-header'
import type { PatientStatus } from '../api/patients-api'
import { useDeactivatePatientMutation } from '../api/use-deactivate-patient-mutation'
import { usePatientQuery } from '../api/use-patient-query'
import { usePatientsQuery } from '../api/use-patients-query'
import { usePatientsSummaryQuery } from '../api/use-patients-summary-query'
import { useReactivatePatientMutation } from '../api/use-reactivate-patient-mutation'
import { useSpeciesQuery } from '../api/use-species-query'
import { PATIENT_POPOVER_TITLE_ID, PatientRowPopover } from './patient-row-popover'
import { PatientSummaryCards } from './patient-summary-cards'
import { PatientTable } from './patient-table'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-list-filters.css'
import '../../attendances/components/attendance-list-page.css'
import '../../attendances/components/attendance-status-tabs.css'

const PAGE_SIZE = 25

const STATUS_TABS: { value: PatientStatus | undefined; label: string }[] = [
  { value: undefined, label: 'Todos' },
  { value: 'ACTIVE', label: 'Ativos' },
  { value: 'INACTIVE', label: 'Inativos' },
]

/** Lista de pacientes no padrão da Operação: busca e ação no cabeçalho, cartões de resumo, abas de
 * status com contagem, filtros com ícone, tabela e resumo (`?paciente=<id>`) em popover. Criar e
 * editar ficam nas páginas `/pacientes/novo` e `/pacientes/:id`. */
export function PatientsPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('patients.manage') ?? false

  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get('paciente')

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<PatientStatus | undefined>(undefined)
  const [clinicId, setClinicId] = useState('')
  const [speciesId, setSpeciesId] = useState('')
  const [page, setPage] = useState(1)

  // A digitação não dispara 3 requisições por tecla (lista e dois resumos): espera 300 ms.
  const debouncedSearch = useDebouncedValue(search, 300)
  const searchTerm = debouncedSearch || undefined
  const clinicFilter = clinicId || undefined
  const speciesFilter = speciesId || undefined

  const listQuery = usePatientsQuery({
    search: searchTerm,
    status,
    clinicId: clinicFilter,
    speciesId: speciesFilter,
    page,
    pageSize: PAGE_SIZE,
  })
  // Cartões: só a busca. Abas: busca + filtros, para a contagem bater com a tabela.
  const cardsSummary = usePatientsSummaryQuery({ search: searchTerm })
  const tabsSummary = usePatientsSummaryQuery({
    search: searchTerm,
    clinicId: clinicFilter,
    speciesId: speciesFilter,
  })
  const detailQuery = usePatientQuery(selectedId)
  const clinicsQuery = useAllClinicsQuery()
  const speciesQuery = useSpeciesQuery()
  const deactivateMutation = useDeactivatePatientMutation()
  const reactivateMutation = useReactivatePatientMutation()

  const clinicNameById = useMemo(
    () => new Map((clinicsQuery.data?.items ?? []).map((clinic) => [clinic.id, clinic.name])),
    [clinicsQuery.data],
  )
  const speciesNameById = useMemo(
    () => new Map((speciesQuery.data ?? []).map((species) => [species.id, species.name])),
    [speciesQuery.data],
  )
  const clinicOptions: DropdownOption[] = [
    { value: '', label: 'Todas' },
    ...(clinicsQuery.data?.items ?? []).map((clinic) => ({ value: clinic.id, label: clinic.name })),
  ]
  const speciesOptions: DropdownOption[] = [
    { value: '', label: 'Todas' },
    ...(speciesQuery.data ?? []).map((species) => ({ value: species.id, label: species.name })),
  ]

  const hasActiveFilters = clinicId !== '' || speciesId !== ''
  const selectedPatient = detailQuery.data ?? null
  const tabCounts = [tabsSummary.data?.total, tabsSummary.data?.active, tabsSummary.data?.inactive]

  function select(id: string | null) {
    setSearchParams(id ? { paciente: id } : {}, { replace: true })
  }

  return (
    <div className="attendance-list-page">
      <PageHeader
        title="Pacientes"
        actions={
          <>
            <label className="attendance-list-page__search">
              <SearchIcon />
              <input
                value={search}
                aria-label="Buscar paciente"
                placeholder="Buscar paciente ou tutor..."
                onChange={(event) => {
                  setSearch(event.target.value)
                  setPage(1)
                }}
              />
            </label>
            {canManage && (
              <Link to="/pacientes/novo" className="button button--primary">
                <PlusIcon /> Novo paciente
              </Link>
            )}
          </>
        }
      />

      <PatientSummaryCards
        total={cardsSummary.data?.total}
        active={cardsSummary.data?.active}
        inactive={cardsSummary.data?.inactive}
      />

      <div className="attendance-list-page__panel">
        <div className="attendance-list-page__filter-row">
          <div className="attendance-status-tabs" role="group" aria-label="Filtrar por status">
            {STATUS_TABS.map((tab, index) => (
              <button
                key={tab.label}
                type="button"
                className="attendance-status-tabs__tab"
                data-active={tab.value === status}
                aria-pressed={tab.value === status}
                onClick={() => {
                  setStatus(tab.value)
                  setPage(1)
                }}
              >
                {tab.label}
                {tabCounts[index] !== undefined ? <b>{tabCounts[index]}</b> : null}
              </button>
            ))}
          </div>
          <div className="attendance-list-filters" role="group" aria-label="Filtros">
            <Dropdown
              label="Clínica"
              icon={<ClinicsIcon />}
              options={clinicOptions}
              value={clinicId}
              searchable
              onChange={(value) => {
                setClinicId(value)
                setPage(1)
              }}
            />
            <Dropdown
              label="Espécie"
              icon={<PatientsIcon />}
              options={speciesOptions}
              value={speciesId}
              onChange={(value) => {
                setSpeciesId(value)
                setPage(1)
              }}
            />
            {hasActiveFilters && (
              <button
                type="button"
                className="attendance-list-filters__clear"
                onClick={() => {
                  setClinicId('')
                  setSpeciesId('')
                  setPage(1)
                }}
              >
                <CloseIcon /> Limpar filtros
              </button>
            )}
          </div>
        </div>

        <PatientTable
          patients={listQuery.data?.items ?? []}
          speciesNameById={speciesNameById}
          clinicNameById={clinicNameById}
          canManage={canManage}
          selectedId={selectedId}
          isLoading={listQuery.isLoading}
          error={listQuery.error}
          page={listQuery.data?.page ?? page}
          pageSize={listQuery.data?.pageSize ?? PAGE_SIZE}
          total={listQuery.data?.total ?? 0}
          onSelect={select}
          onDeactivate={(id) => deactivateMutation.mutate(id)}
          onReactivate={(id) => reactivateMutation.mutate(id)}
          onPageChange={setPage}
        />
      </div>

      {selectedId !== null && (
        <Modal
          titleId={PATIENT_POPOVER_TITLE_ID}
          size="md"
          dismissOnBackdrop
          className="attendance-popover"
          onClose={() => select(null)}
        >
          <PatientRowPopover
            patient={selectedPatient}
            isLoading={detailQuery.isLoading}
            loadError={detailQuery.error}
            speciesName={
              selectedPatient ? (speciesNameById.get(selectedPatient.speciesId) ?? '—') : '—'
            }
            clinicName={
              selectedPatient?.clinicId ? (clinicNameById.get(selectedPatient.clinicId) ?? '—') : '—'
            }
            canManage={canManage}
            onClose={() => select(null)}
            onDeactivate={(id) => deactivateMutation.mutate(id)}
            onReactivate={(id) => reactivateMutation.mutate(id)}
          />
        </Modal>
      )}
    </div>
  )
}
