import { useState } from 'react'

import { ApiError } from '../../../shared/api/errors'
import { SelectField, type SelectOption } from '../../../shared/ui/select'
import { useAuth } from '../../auth/auth-context'
import { useClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useMonthlyClosuresQuery } from '../api/use-monthly-closures-query'
import { ClosuresListPagination } from './closures-list-pagination'
import { ClosuresListTable } from './closures-list-table'
import './closures-list-page.css'

const PAGE_SIZE = 20

export function ClosuresListPage() {
  const { user } = useAuth()
  const canRead = user?.permissions.includes('closures.read') ?? false

  const [page, setPage] = useState(1)
  const [clinicId, setClinicId] = useState('')

  const clinicsQuery = useClinicsQuery({ pageSize: 100 })
  const clinicOptions: SelectOption[] = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
  const clinicNameById: Record<string, string> = Object.fromEntries(
    (clinicsQuery.data?.items ?? []).map((clinic) => [clinic.id, clinic.name]),
  )

  const closuresQuery = useMonthlyClosuresQuery(
    canRead ? { clinicId: clinicId || undefined, page, pageSize: PAGE_SIZE } : { page: 1, pageSize: 0 },
  )

  const isForbidden = closuresQuery.error instanceof ApiError && closuresQuery.error.status === 403
  const isGenericError = closuresQuery.isError && !isForbidden
  const isLoading = canRead && closuresQuery.isLoading

  return (
    <div className="closures-list-page">
      <div className="closures-list-page__header">
        <div className="closures-list-page__eyebrow">Financeiro</div>
        <h1 className="closures-list-page__title">Fechamentos</h1>
      </div>

      {!canRead ? (
        <p className="closures-list-page__forbidden">
          Você não tem permissão para visualizar fechamentos.
        </p>
      ) : (
        <>
          <div className="closures-list-page__filters">
            <SelectField
              id="closures-list-clinic"
              label="Clínica"
              options={[{ value: '', label: 'Todas as clínicas' }, ...clinicOptions]}
              value={clinicId}
              onChange={(event) => {
                setClinicId(event.target.value)
                setPage(1)
              }}
            />
          </div>

          <div className="closures-list-page__body">
            {isLoading && <p className="closures-list-page__hint">Carregando…</p>}

            {isForbidden && (
              <p className="closures-list-page__forbidden">
                Você não tem permissão para visualizar fechamentos.
              </p>
            )}

            {isGenericError && (
              <p className="closures-list-page__error">
                Não foi possível carregar os fechamentos. Tente novamente.
              </p>
            )}

            {!isLoading && closuresQuery.data && (
              <>
                <ClosuresListTable closures={closuresQuery.data.items} clinicNameById={clinicNameById} />
                <ClosuresListPagination
                  page={closuresQuery.data.page}
                  pageSize={closuresQuery.data.pageSize}
                  total={closuresQuery.data.total}
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
