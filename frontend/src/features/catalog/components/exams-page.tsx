import { useState } from 'react'
import { Link } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { Dropdown } from '../../../shared/ui/dropdown'
import { CloseIcon, ExamsIcon, PatientsIcon, PlusIcon, SearchIcon, TagIcon } from '../../../shared/ui/icons'
import { Modal } from '../../../shared/ui/modal'
import { PageHeader } from '../../../shared/ui/page-header'
import { Pagination } from '../../../shared/ui/pagination'
import type { ExamStatus } from '../api/catalog-api'
import { useActiveExamCategoriesQuery } from '../api/use-active-exam-categories-query'
import { useDeactivateExamMutation } from '../api/use-deactivate-exam-mutation'
import { useExamsQuery } from '../api/use-exams-query'
import { ExamImportButton } from './exam-import-button'
import { EXAM_POPOVER_TITLE_ID, ExamRowPopover } from './exam-row-popover'
import { ExamTable } from './exam-table'
import { OnCallFeeSettingsPanel } from './on-call-fee-settings-panel'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-status-tabs.css'
import './exams-page.css'

type Tab = 'exams' | 'fees'

const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'ACTIVE', label: 'Ativos' },
  { value: 'INACTIVE', label: 'Inativos' },
]

export function ExamsPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('catalog.manage') ?? false
  const canCreate = canManage && (user?.permissions.includes('pricing.manage') ?? false)
  const priceVisible = user?.permissions.includes('pricing.read') ?? false

  const [tab, setTab] = useState<Tab>('exams')
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [speciesId, setSpeciesId] = useState('')
  const [status, setStatus] = useState<ExamStatus | ''>('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Busca, categoria, espécie e status filtram no servidor; a contagem vem do total paginado.
  const listQuery = useExamsQuery({
    search: search || undefined,
    categoryId: categoryId || undefined,
    speciesId: speciesId || undefined,
    status: status || undefined,
    page,
    pageSize: 25,
  })
  const categoriesQuery = useActiveExamCategoriesQuery()
  const speciesQuery = useSpeciesQuery()
  const deactivateMutation = useDeactivateExamMutation()

  const categories = categoriesQuery.data ?? []
  const species = speciesQuery.data ?? []
  const selectedExam = listQuery.data?.items.find((exam) => exam.id === selectedId) ?? null
  const hasActiveFilters = categoryId !== '' || speciesId !== '' || status !== ''

  function change<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value)
      setPage(1)
    }
  }

  function clearFilters() {
    setCategoryId('')
    setSpeciesId('')
    setStatus('')
    setPage(1)
  }

  return (
    <div className="exams-page">
      <PageHeader
        title="Exames & Preços"
        actions={
          <>
            {tab === 'exams' && (
              <label className="exams-page__search">
                <SearchIcon />
                <input
                  value={search}
                  aria-label="Buscar exame"
                  placeholder="Buscar nome ou código..."
                  onChange={(event) => change(setSearch)(event.target.value)}
                />
              </label>
            )}
            {tab === 'exams' && canManage && <ExamImportButton />}
            {tab === 'exams' && canManage && (
              <Link to="/cadastros/exames/novo-pacote" className="button button--secondary">
                <PlusIcon /> Novo pacote
              </Link>
            )}
            {tab === 'exams' && canCreate && (
              <Link to="/cadastros/exames/novo" className="button button--primary">
                <PlusIcon /> Novo exame
              </Link>
            )}
          </>
        }
      />

      <div className="exams-page__panel">
        <div className="exams-page__filter-row">
          <div className="attendance-status-tabs" role="tablist" aria-label="Seções">
            <button
              type="button"
              role="tab"
              id="exams-tab-exams"
              aria-selected={tab === 'exams'}
              aria-controls="exams-panel"
              className="attendance-status-tabs__tab"
              data-active={tab === 'exams'}
              onClick={() => setTab('exams')}
            >
              Exames
              {listQuery.data ? <b>{listQuery.data.total}</b> : null}
            </button>
            <button
              type="button"
              role="tab"
              id="exams-tab-fees"
              aria-selected={tab === 'fees'}
              aria-controls="exams-panel"
              className="attendance-status-tabs__tab"
              data-active={tab === 'fees'}
              onClick={() => setTab('fees')}
            >
              Taxas de plantão
            </button>
          </div>

          {tab === 'exams' && (
            <div className="exams-page__filters" role="group" aria-label="Filtros">
              <Dropdown
                label="Categoria"
                icon={<TagIcon />}
                options={[
                  { value: '', label: 'Todas' },
                  ...categories.map((category) => ({ value: category.id, label: category.name })),
                ]}
                value={categoryId}
                onChange={change(setCategoryId)}
              />
              <Dropdown
                label="Espécie"
                icon={<PatientsIcon />}
                options={[
                  { value: '', label: 'Todas' },
                  ...species.map((item) => ({ value: item.id, label: item.name })),
                ]}
                value={speciesId}
                onChange={change(setSpeciesId)}
              />
              <Dropdown
                label="Status"
                icon={<ExamsIcon />}
                options={STATUS_OPTIONS}
                value={status}
                onChange={(value) => change(setStatus)(value as ExamStatus | '')}
              />
              {hasActiveFilters && (
                <button type="button" className="exams-page__clear" onClick={clearFilters}>
                  <CloseIcon /> Limpar filtros
                </button>
              )}
            </div>
          )}
        </div>

        <div
          id="exams-panel"
          role="tabpanel"
          aria-labelledby={tab === 'exams' ? 'exams-tab-exams' : 'exams-tab-fees'}
        >
          {tab === 'fees' && <OnCallFeeSettingsPanel />}
          {tab === 'exams' && (
            <>
              <ExamTable
                exams={listQuery.data?.items ?? []}
                categories={categories}
                species={species}
                isLoading={listQuery.isLoading}
                isError={listQuery.isError}
                canManage={canManage}
                priceVisible={priceVisible}
                selectedId={selectedExam?.id ?? null}
                onRowClick={setSelectedId}
                onDeactivate={(examId) => deactivateMutation.mutate(examId)}
              />
              <Pagination
                itemLabel={['exame', 'exames']}
                page={listQuery.data?.page ?? page}
                pageSize={listQuery.data?.pageSize ?? 25}
                total={listQuery.data?.total ?? 0}
                onPageChange={setPage}
              />
            </>
          )}
        </div>
      </div>

      {selectedExam && (
        <Modal
          size="md"
          dismissOnBackdrop
          className="attendance-popover"
          titleId={EXAM_POPOVER_TITLE_ID}
          onClose={() => setSelectedId(null)}
        >
          <ExamRowPopover
            exam={selectedExam}
            categories={categories}
            species={species}
            canManage={canManage}
            onClose={() => setSelectedId(null)}
            onDeactivate={(examId) => {
              deactivateMutation.mutate(examId)
              setSelectedId(null)
            }}
          />
        </Modal>
      )}
    </div>
  )
}
