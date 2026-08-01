import { useState } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { PlusIcon } from '../../../shared/ui/icons'
import type { SelectOption } from '../../../shared/ui/select'
import { useAuth } from '../../auth/auth-context'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useAllPatientsQuery } from '../../patients/api/use-patients-query'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { useAllVeterinariansQuery } from '../../veterinarians/api/use-veterinarians-query'
import type { AttendanceStatus } from '../api/attendances-api'
import { useAttendancesQuery } from '../api/use-attendances-query'
import { AttendanceListFilters } from './attendance-list-filters'
import { AttendanceListPagination } from './attendance-list-pagination'
import { AttendanceListTable, type PatientDisplay } from './attendance-list-table'
import './attendance-list-page.css'

const PAGE_SIZE = 20

export function AttendanceListPage() {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('attendances.read') ?? false
  const canCreate = user?.permissions.includes('attendances.create') ?? false

  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<AttendanceStatus | ''>('')
  const [clinicId, setClinicId] = useState('')
  const [veterinarianId, setVeterinarianId] = useState('')
  const [protocolNumber, setProtocolNumber] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [serviceDateFrom, setServiceDateFrom] = useState('')
  const [serviceDateTo, setServiceDateTo] = useState('')

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
          veterinarianId: veterinarianId || undefined,
          protocolNumber: protocolNumber.trim() || undefined,
          ownerName: ownerName.trim() || undefined,
          serviceDateFrom: serviceDateFrom || undefined,
          serviceDateTo: serviceDateTo || undefined,
        }
      : null,
  )

  const clinicOptions: SelectOption[] = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const veterinarianOptions: SelectOption[] = (veterinariansQuery.data?.items ?? []).map(
    (veterinarian) => ({ value: veterinarian.id, label: veterinarian.name }),
  )

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
      const detailParts = [speciesNameById[patient.speciesId], patient.ageDescription].filter(
        (part): part is string => Boolean(part),
      )
      return [patient.id, { name: patient.name, detail: detailParts.join(' · ') }]
    }),
  )

  const isForbidden = attendancesQuery.error instanceof ApiError && attendancesQuery.error.status === 403
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
        {canCreate && (
          <Link to="/operacao/novo" className="button button--primary">
            <PlusIcon /> Novo protocolo
          </Link>
        )}
      </div>

      {!canRead ? (
        <p className="attendance-list-page__forbidden">
          Você não tem permissão para visualizar atendimentos.
        </p>
      ) : (
        <>
          <AttendanceListFilters
            clinicOptions={clinicOptions}
            veterinarianOptions={veterinarianOptions}
            clinicId={clinicId}
            veterinarianId={veterinarianId}
            status={status}
            protocolNumber={protocolNumber}
            ownerName={ownerName}
            serviceDateFrom={serviceDateFrom}
            serviceDateTo={serviceDateTo}
            disabled={isLoading}
            onClinicChange={(value) => handleFilterChange(() => setClinicId(value))}
            onVeterinarianChange={(value) => handleFilterChange(() => setVeterinarianId(value))}
            onStatusChange={(value) => handleFilterChange(() => setStatus(value))}
            onProtocolNumberChange={(value) =>
              handleFilterChange(() => setProtocolNumber(value))
            }
            onOwnerNameChange={(value) => handleFilterChange(() => setOwnerName(value))}
            onServiceDateFromChange={(value) =>
              handleFilterChange(() => setServiceDateFrom(value))
            }
            onServiceDateToChange={(value) =>
              handleFilterChange(() => setServiceDateTo(value))
            }
          />

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
        </>
      )}
    </div>
  )
}
