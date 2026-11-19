import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { useActionError } from '../../../shared/lib/use-action-error'
import { Modal } from '../../../shared/ui/modal'
import { PlusIcon, SearchIcon } from '../../../shared/ui/icons'
import { PageHeader } from '../../../shared/ui/page-header'
import type { ClinicStatus } from '../api/clinics-api'
import { useClinicQuery } from '../api/use-clinic-query'
import { useClinicsQuery } from '../api/use-clinics-query'
import { useDeactivateClinicMutation } from '../api/use-deactivate-clinic-mutation'
import { ClinicDetail } from './clinic-detail'
import { ClinicTable } from './clinic-table'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-list-page.css'
import '../../attendances/components/attendance-status-tabs.css'

const STATUS_TABS: { value: ClinicStatus | undefined; label: string }[] = [
  { value: undefined, label: 'Todas' },
  { value: 'ACTIVE', label: 'Ativas' },
  { value: 'SPECIAL', label: 'Especiais' },
  { value: 'DELINQUENT', label: 'Negativadas' },
  { value: 'INACTIVE', label: 'Inativas' },
]

/** Lista de clínicas no padrão da Operação: busca e ação no cabeçalho, abas de status com
 * contagem, tabela e resumo (`?clinica=<id>`) em popover. Criar e editar ficam em `ClinicFormPage`. */
export function ClinicsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const canManage = user?.permissions.includes('clinics.manage') ?? false

  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get('clinica')

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<ClinicStatus | undefined>(undefined)
  const [page, setPage] = useState(1)

  const listQuery = useClinicsQuery({ search: search || undefined, status, page, pageSize: 25 })
  // Contagem de cada aba com o mesmo termo de busca, vinda do servidor.
  const searchTerm = search || undefined
  const counts = [
    useClinicsQuery({ search: searchTerm, page: 1, pageSize: 1 }),
    useClinicsQuery({ search: searchTerm, status: 'ACTIVE', page: 1, pageSize: 1 }),
    useClinicsQuery({ search: searchTerm, status: 'SPECIAL', page: 1, pageSize: 1 }),
    useClinicsQuery({ search: searchTerm, status: 'DELINQUENT', page: 1, pageSize: 1 }),
    useClinicsQuery({ search: searchTerm, status: 'INACTIVE', page: 1, pageSize: 1 }),
  ]
  const detailQuery = useClinicQuery(selectedId)
  const deactivateMutation = useDeactivateClinicMutation()
  const actionError = useActionError()

  function select(id: string | null) {
    setSearchParams(id ? { clinica: id } : {}, { replace: true })
  }

  return (
    <div className="attendance-list-page">
      <PageHeader
        title="Clínicas parceiras"
        actions={
          <>
            <label className="attendance-list-page__search">
              <SearchIcon />
              <input
                value={search}
                aria-label="Buscar clínica"
                placeholder="Buscar nome, CNPJ ou cidade..."
                onChange={(event) => {
                  setSearch(event.target.value)
                  setPage(1)
                }}
              />
            </label>
            {canManage && (
              <Link to="/cadastros/clinicas/nova" className="button button--primary">
                <PlusIcon /> Nova clínica
              </Link>
            )}
          </>
        }
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
                {counts[index]?.data ? <b>{counts[index].data.total}</b> : null}
              </button>
            ))}
          </div>
        </div>

        {actionError.message && (
          <p role="alert" className="attendance-list-page__error">
            {actionError.message}
          </p>
        )}
        <ClinicTable
          clinics={listQuery.data?.items ?? []}
          canManage={canManage}
          selectedId={selectedId}
          isLoading={listQuery.isLoading}
          isError={listQuery.isError}
          page={listQuery.data?.page ?? page}
          pageSize={listQuery.data?.pageSize ?? 25}
          total={listQuery.data?.total ?? 0}
          onSelect={select}
          onEdit={(id) => navigate(`/cadastros/clinicas/${id}/editar`)}
          onPageChange={setPage}
        />
      </div>

      {selectedId !== null && (
        <Modal
          titleId="clinic-detail-title"
          size="md"
          dismissOnBackdrop
          className="attendance-popover"
          onClose={() => select(null)}
        >
          <ClinicDetail
            clinic={detailQuery.data ?? null}
            isLoading={detailQuery.isLoading}
            canManage={canManage}
            actionError={actionError.message}
            onClose={() => select(null)}
            onDeactivate={() => {
              actionError.clear()
              deactivateMutation.mutate(selectedId, { onError: actionError.onError })
            }}
          />
        </Modal>
      )}
    </div>
  )
}
