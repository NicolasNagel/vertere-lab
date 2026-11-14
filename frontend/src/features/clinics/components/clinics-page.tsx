import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { PlusIcon } from '../../../shared/ui/icons'
import { PageHeader } from '../../../shared/ui/page-header'
import type { ClinicStatus } from '../api/clinics-api'
import { useClinicQuery } from '../api/use-clinic-query'
import { useClinicsQuery } from '../api/use-clinics-query'
import { useDeactivateClinicMutation } from '../api/use-deactivate-clinic-mutation'
import { ClinicDetail } from './clinic-detail'
import { ClinicTable } from './clinic-table'
import '../../../shared/ui/button.css'
import './clinics-page.css'

/** Tela de consulta: tabela de clínicas + painel de detalhe (`?clinica=<id>`).
 * Criar e editar ficam na tela de formulário (`ClinicFormPage`). */
export function ClinicsPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('clinics.manage') ?? false

  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get('clinica')

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<ClinicStatus | undefined>(undefined)
  const [page, setPage] = useState(1)

  const listQuery = useClinicsQuery({ search: search || undefined, status, page, pageSize: 25 })
  const detailQuery = useClinicQuery(selectedId)
  const deactivateMutation = useDeactivateClinicMutation()

  const clinics = listQuery.data?.items ?? []
  const activeCount = clinics.filter((clinic) => clinic.status === 'ACTIVE').length

  function select(id: string | null) {
    setSearchParams(id ? { clinica: id } : {}, { replace: true })
  }

  return (
    <div className="clinics-page">
      <PageHeader
        title="Clínicas parceiras"
        actions={
          canManage && (
            <Link to="/cadastros/clinicas/nova" className="button button--primary">
              <PlusIcon /> Nova clínica
            </Link>
          )
        }
      />

      <div className="clinics-page__body" data-with-detail={selectedId !== null}>
        <ClinicTable
          clinics={clinics}
          activeCount={activeCount}
          canManage={canManage}
          selectedId={selectedId}
          search={search}
          status={status}
          isLoading={listQuery.isLoading}
          isError={listQuery.isError}
          page={listQuery.data?.page ?? page}
          pageSize={listQuery.data?.pageSize ?? 25}
          total={listQuery.data?.total ?? 0}
          onSearchChange={(value) => {
            setSearch(value)
            setPage(1)
          }}
          onStatusChange={(value) => {
            setStatus(value)
            setPage(1)
          }}
          onSelect={select}
          onPageChange={setPage}
        />

        {selectedId !== null && (
          <ClinicDetail
            clinic={detailQuery.data ?? null}
            isLoading={detailQuery.isLoading}
            canManage={canManage}
            onClose={() => select(null)}
            onDeactivate={() => deactivateMutation.mutate(selectedId)}
          />
        )}
      </div>
    </div>
  )
}
