import { useState } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { useDebouncedValue } from '../../../shared/lib/use-debounced-value'
import { PlusIcon, SearchIcon } from '../../../shared/ui/icons'
import type { SelectOption } from '../../../shared/ui/select'
import { useAuth } from '../../auth/auth-context'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useAllPatientsQuery } from '../../patients/api/use-patients-query'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { useAllVeterinariansQuery } from '../../veterinarians/api/use-veterinarians-query'
import type { AttendanceStatus, ServiceLevel } from '../api/attendances-api'
import { useAttendanceStatusCountsQuery } from '../api/use-attendance-status-counts-query'
import { useAttendancesQuery } from '../api/use-attendances-query'
import { AttendanceListFilters } from './attendance-list-filters'
import { AttendanceListPagination } from './attendance-list-pagination'
import { AttendanceListTable, type PatientDisplay } from './attendance-list-table'
import { AttendanceStatusTabs } from './attendance-status-tabs'
import { AttendanceSummaryCards } from './attendance-summary-cards'
import '../../../shared/ui/button.css'
import './attendance-list-page.css'

const PAGE_SIZE = 20

export function AttendanceListPage() {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('attendances.read') ?? false
  const canCreate = user?.permissions.includes('attendances.create') ?? false

  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<AttendanceStatus | ''>('')
  const [clinicId, setClinicId] = useState('')
  const [serviceLevel, setServiceLevel] = useState<ServiceLevel | ''>('')
  const [protocolNumber, setProtocolNumber] = useState('')
  const [serviceDateFrom, setServiceDateFrom] = useState('')
  const [serviceDateTo, setServiceDateTo] = useState('')

  const debouncedProtocolNumber = useDebouncedValue(protocolNumber.trim(), 300)

  const clinicsQuery = useAllClinicsQuery()
  const veterinariansQuery = useAllVeterinariansQuery()
  const patientsQuery = useAllPatientsQuery()
  const speciesQuery = useSpeciesQuery()

  const attendancesQuery = useAttendancesQuery(
    canRead
      ? {
          page,
          pageSize: PAGE_SIZE,
          status: status || undefined,
          clinicId: clinicId || undefined,
          serviceLevel: serviceLevel || undefined,
          protocolNumber: debouncedProtocolNumber || undefined,
          serviceDateFrom: serviceDateFrom || undefined,
          serviceDateTo: serviceDateTo || undefined,
        }
      : null,
  )
  const statusCountsQuery = useAttendanceStatusCountsQuery(
    canRead
      ? {
          clinicId: clinicId || undefined,
          serviceLevel: serviceLevel || undefined,
          protocolNumber: debouncedProtocolNumber || undefined,
          serviceDateFrom: serviceDateFrom || undefined,
          serviceDateTo: serviceDateTo || undefined,
        }
      : null,
  )

  const clinicOptions: SelectOption[] = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const clinicNameById: Record<string, string> = Object.fromEntries(
    (clinicsQuery.data?.items ?? []).map((clinic) => [clinic.id, clinic.name]),
  )
  const veterinarianNameById: Record<string, string> = Object.fromEntries(
    (veterinariansQuery.data?.items ?? []).map((veterinarian) => [
      veterinarian.id,
      veterinarian.name,
    ]),
  )
  const speciesNameById: Record<string, string> = Object.fromEntries(
    (speciesQuery.data ?? []).map((species) => [species.id, species.name]),
  )
  const patientDisplayById: Record<string, PatientDisplay> = Object.fromEntries(
    (patientsQuery.data?.items ?? []).map((patient) => {
      const sexLabel = patient.sex === 'MALE' ? 'Macho' : 'Fêmea'
      const detail = [speciesNameById[patient.speciesId], sexLabel, patient.ageDescription]
        .filter((part): part is string => Boolean(part))
        .join(' · ')
      return [patient.id, { name: patient.name, detail, sex: patient.sex }]
    }),
  )

  const lookupsFailed =
    clinicsQuery.isError ||
    veterinariansQuery.isError ||
    patientsQuery.isError ||
    speciesQuery.isError
  const isForbidden =
    attendancesQuery.error instanceof ApiError && attendancesQuery.error.status === 403
  const isGenericError = attendancesQuery.isError && !isForbidden
  const isLoading = canRead && attendancesQuery.isLoading

  function handleFilterChange(update: () => void) {
    update()
    setPage(1)
  }

  return (
    <div className="attendance-list-page">
      <div className="attendance-list-page__header">
        <div>
          <div className="attendance-list-page__eyebrow">Operação</div>
          <h1 className="attendance-list-page__title">Registro de Atendimentos</h1>
        </div>
        {canRead && (
          <div className="attendance-list-page__header-actions">
            <label className="attendance-list-page__search">
              <SearchIcon />
              <input
                value={protocolNumber}
                maxLength={32}
                placeholder="Buscar protocolo..."
                onChange={(event) =>
                  handleFilterChange(() => setProtocolNumber(event.target.value))
                }
              />
            </label>
            {canCreate && (
              <Link to="/operacao/novo" className="button button--primary">
                <PlusIcon /> Novo protocolo
              </Link>
            )}
          </div>
        )}
      </div>

      {!canRead ? (
        <p className="attendance-list-page__forbidden">
          Você não tem permissão para visualizar atendimentos.
        </p>
      ) : (
        <>
          <AttendanceSummaryCards counts={statusCountsQuery.data} />

          <div className="attendance-list-page__panel">
            <div className="attendance-list-page__filter-row">
              <AttendanceStatusTabs
                counts={statusCountsQuery.data}
                value={status}
                onChange={(value) => handleFilterChange(() => setStatus(value))}
              />
              <AttendanceListFilters
                clinicOptions={clinicOptions}
                clinicId={clinicId}
                serviceLevel={serviceLevel}
                disabled={isLoading}
                onClinicChange={(value) => handleFilterChange(() => setClinicId(value))}
                onServiceLevelChange={(value) => handleFilterChange(() => setServiceLevel(value))}
                onServiceDateFromChange={(value) =>
                  handleFilterChange(() => setServiceDateFrom(value))
                }
                onServiceDateToChange={(value) => handleFilterChange(() => setServiceDateTo(value))}
              />
            </div>

            <div className="attendance-list-page__body">
              {isLoading && <p className="attendance-list-page__hint">Carregando…</p>}

              {isForbidden && (
                <p className="attendance-list-page__forbidden">
                  Você não tem permissão para visualizar atendimentos.
                </p>
              )}

              {isGenericError && (
                <p className="attendance-list-page__error">
                  Não foi possível carregar os atendimentos. Tente novamente.
                </p>
              )}

              {lookupsFailed && (
                <p className="attendance-list-page__error" role="status">
                  Não foi possível carregar nomes de clínicas, veterinários ou pacientes. Os campos
                  afetados aparecem como "—".
                </p>
              )}

              {!isLoading && attendancesQuery.data && (
                <>
                  <AttendanceListTable
                    attendances={attendancesQuery.data.items}
                    clinicNameById={clinicNameById}
                    veterinarianNameById={veterinarianNameById}
                    patientDisplayById={patientDisplayById}
                  />
                  <AttendanceListPagination
                    page={attendancesQuery.data.page}
                    pageSize={attendancesQuery.data.pageSize}
                    total={attendancesQuery.data.total}
                    onPageChange={setPage}
                  />
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
