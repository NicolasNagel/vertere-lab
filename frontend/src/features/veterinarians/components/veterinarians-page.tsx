import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { useActionError } from '../../../shared/lib/use-action-error'
import { Dropdown } from '../../../shared/ui/dropdown'
import { ClinicsIcon, CloseIcon, PlusIcon, SearchIcon } from '../../../shared/ui/icons'
import { Modal } from '../../../shared/ui/modal'
import { PageHeader } from '../../../shared/ui/page-header'
import type { VeterinarianStatus } from '../api/veterinarians-api'
import { useDeactivateVeterinarianMutation } from '../api/use-deactivate-veterinarian-mutation'
import { useVeterinarianQuery } from '../api/use-veterinarian-query'
import { useVeterinariansQuery } from '../api/use-veterinarians-query'
import { VETERINARIAN_POPOVER_TITLE_ID, VeterinarianRowPopover } from './veterinarian-row-popover'
import { VeterinarianSummaryCards } from './veterinarian-summary-cards'
import { VeterinarianTable } from './veterinarian-table'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-list-filters.css'
import '../../attendances/components/attendance-list-page.css'
import '../../attendances/components/attendance-status-tabs.css'

type LinkFilter = '' | 'linked' | 'autonomous'

const STATUS_TABS: { value: VeterinarianStatus | undefined; label: string }[] = [
  { value: undefined, label: 'Todos' },
  { value: 'ACTIVE', label: 'Ativos' },
  { value: 'INACTIVE', label: 'Inativos' },
]

const LINK_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'linked', label: 'Vinculados' },
  { value: 'autonomous', label: 'Autônomos' },
]

/** Lista de veterinários no padrão da Operação: busca e ação no cabeçalho, cartões de resumo,
 * abas de status com contagem, filtro com ícone, tabela e resumo (`?veterinario=<id>`) em
 * popover. Criar fica em `VeterinarianFormPage`; editar, nos blocos do detalhe. */
export function VeterinariansPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('veterinarians.manage') ?? false

  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get('veterinario')

  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<VeterinarianStatus | undefined>(undefined)
  const [link, setLink] = useState<LinkFilter>('')
  const [page, setPage] = useState(1)

  const isAutonomous = link === 'autonomous' ? true : link === 'linked' ? false : undefined
  const searchTerm = search || undefined

  const listQuery = useVeterinariansQuery({
    search: searchTerm,
    status,
    isAutonomous,
    page,
    pageSize: 25,
  })
  // Contagens do servidor com o mesmo termo de busca (e o filtro de vínculo, nas abas).
  const tabCounts = [
    useVeterinariansQuery({
      search: searchTerm,
      isAutonomous,
      page: 1,
      pageSize: 1,
    }),
    useVeterinariansQuery({
      search: searchTerm,
      isAutonomous,
      status: 'ACTIVE',
      page: 1,
      pageSize: 1,
    }),
    useVeterinariansQuery({
      search: searchTerm,
      isAutonomous,
      status: 'INACTIVE',
      page: 1,
      pageSize: 1,
    }),
  ]
  const summaryTotal = useVeterinariansQuery({
    search: searchTerm,
    page: 1,
    pageSize: 1,
  })
  const summaryActive = useVeterinariansQuery({
    search: searchTerm,
    status: 'ACTIVE',
    page: 1,
    pageSize: 1,
  })
  const summaryAutonomous = useVeterinariansQuery({
    search: searchTerm,
    isAutonomous: true,
    page: 1,
    pageSize: 1,
  })
  const detailQuery = useVeterinarianQuery(selectedId)
  const deactivateMutation = useDeactivateVeterinarianMutation()
  const actionError = useActionError()

  function deactivate(id: string) {
    actionError.clear()
    deactivateMutation.mutate(id, { onError: actionError.onError })
  }

  const hasActiveFilters = link !== ''

  function select(id: string | null) {
    setSearchParams(id ? { veterinario: id } : {}, { replace: true })
  }

  return (
    <div className="attendance-list-page">
      <PageHeader
        title="Veterinários"
        actions={
          <>
            <label className="attendance-list-page__search">
              <SearchIcon />
              <input
                value={search}
                aria-label="Buscar veterinário"
                placeholder="Buscar nome ou CRMV..."
                onChange={(event) => {
                  setSearch(event.target.value)
                  setPage(1)
                }}
              />
            </label>
            {canManage && (
              <Link to="/cadastros/veterinarios/novo" className="button button--primary">
                <PlusIcon /> Novo veterinário
              </Link>
            )}
          </>
        }
      />

      <VeterinarianSummaryCards
        total={summaryTotal.data?.total}
        active={summaryActive.data?.total}
        autonomous={summaryAutonomous.data?.total}
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
                {tabCounts[index]?.data ? <b>{tabCounts[index].data.total}</b> : null}
              </button>
            ))}
          </div>
          <div className="attendance-list-filters" role="group" aria-label="Filtros">
            <Dropdown
              label="Vínculo"
              icon={<ClinicsIcon />}
              options={LINK_OPTIONS}
              value={link}
              onChange={(value) => {
                setLink(value as LinkFilter)
                setPage(1)
              }}
            />
            {hasActiveFilters && (
              <button
                type="button"
                className="attendance-list-filters__clear"
                onClick={() => {
                  setLink('')
                  setPage(1)
                }}
              >
                <CloseIcon /> Limpar filtros
              </button>
            )}
          </div>
        </div>

        {actionError.message && (
          <p role="alert" className="attendance-list-page__error">
            {actionError.message}
          </p>
        )}
        <VeterinarianTable
          veterinarians={listQuery.data?.items ?? []}
          canManage={canManage}
          selectedId={selectedId}
          isLoading={listQuery.isLoading}
          isError={listQuery.isError}
          page={listQuery.data?.page ?? page}
          pageSize={listQuery.data?.pageSize ?? 25}
          total={listQuery.data?.total ?? 0}
          onSelect={select}
          onDeactivate={deactivate}
          onPageChange={setPage}
        />
      </div>

      {selectedId !== null && (
        <Modal
          titleId={VETERINARIAN_POPOVER_TITLE_ID}
          size="md"
          dismissOnBackdrop
          className="attendance-popover"
          onClose={() => select(null)}
        >
          <VeterinarianRowPopover
            veterinarian={detailQuery.data ?? null}
            isLoading={detailQuery.isLoading}
            canManage={canManage}
            onClose={() => select(null)}
            onDeactivate={(id) => {
              deactivate(id)
              select(null)
            }}
          />
        </Modal>
      )}
    </div>
  )
}
