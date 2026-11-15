import { useState } from 'react'
import { Link } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { AttendanceListPagination } from '../../attendances/components/attendance-list-pagination'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { Dropdown } from '../../../shared/ui/dropdown'
import {
  ClinicsIcon,
  CloseIcon,
  ExamsIcon,
  PatientsIcon,
  PlusIcon,
  SearchIcon,
  TagIcon,
} from '../../../shared/ui/icons'
import { Modal } from '../../../shared/ui/modal'
import { PageHeader } from '../../../shared/ui/page-header'
import type { ExamStatus } from '../api/catalog-api'
import { useActiveExamCategoriesQuery } from '../api/use-active-exam-categories-query'
import { useDeactivateExamMutation } from '../api/use-deactivate-exam-mutation'
import { useExamsQuery } from '../api/use-exams-query'
import { ClinicFeeRulesPanel } from './clinic-fee-rules-panel'
import { ExamImportButton } from './exam-import-button'
import { ExamListSummaryCards } from './exam-list-summary-cards'
import { EXAM_POPOVER_TITLE_ID, ExamRowPopover } from './exam-row-popover'
import { ExamTable } from './exam-table'
import { OnCallFeeSettingsPanel } from './on-call-fee-settings-panel'
import { UrgencyFeePanel } from './urgency-fee-panel'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-list-filters.css'
import '../../attendances/components/attendance-list-page.css'
import '../../attendances/components/attendance-list-pagination.css'
import '../../attendances/components/attendance-status-tabs.css'
import './exams-page.css'

type Tab = 'exams' | 'onCall' | 'urgency' | 'clinics'

const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'ACTIVE', label: 'Ativos' },
  { value: 'INACTIVE', label: 'Inativos' },
]

export function ExamsPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('catalog.manage') ?? false
  const canManagePricing = user?.permissions.includes('pricing.manage') ?? false
  const canCreate = canManage && canManagePricing
  const priceVisible = user?.permissions.includes('pricing.read') ?? false

  const [tab, setTab] = useState<Tab>('exams')
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [speciesId, setSpeciesId] = useState('')
  const [status, setStatus] = useState<ExamStatus | ''>('')
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [clinicFilter, setClinicFilter] = useState('')
  const [creatingClinicFee, setCreatingClinicFee] = useState(false)

  // Busca, categoria, espécie e status filtram no servidor; a contagem vem do total paginado.
  const filters = {
    search: search || undefined,
    categoryId: categoryId || undefined,
    speciesId: speciesId || undefined,
  }
  const listQuery = useExamsQuery({
    ...filters,
    status: status || undefined,
    page,
    pageSize: 25,
  })
  const activeCount = useExamsQuery({
    ...filters,
    status: 'ACTIVE',
    page: 1,
    pageSize: 1,
  })
  const inactiveCount = useExamsQuery({
    ...filters,
    status: 'INACTIVE',
    page: 1,
    pageSize: 1,
  })
  const categoriesQuery = useActiveExamCategoriesQuery()
  const speciesQuery = useSpeciesQuery()
  const clinicsQuery = useAllClinicsQuery({ status: 'ACTIVE' })
  const deactivateMutation = useDeactivateExamMutation()

  const categories = categoriesQuery.data ?? []
  const species = speciesQuery.data ?? []
  const clinicOptions = (clinicsQuery.data?.items ?? []).map((clinic) => ({
    value: clinic.id,
    label: clinic.name,
  }))
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

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: 'exams', label: 'Exames', count: listQuery.data?.total },
    { id: 'onCall', label: 'Plantão' },
    { id: 'urgency', label: 'Urgência' },
    { id: 'clinics', label: 'Por clínica' },
  ]

  return (
    <div className="attendance-list-page exams-page">
      <PageHeader
        title="Exames & Preços"
        actions={
          <>
            {tab === 'exams' && (
              <label className="attendance-list-page__search">
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
            {tab === 'clinics' && canManagePricing && (
              <button
                type="button"
                className="button button--primary"
                onClick={() => setCreatingClinicFee(true)}
              >
                <PlusIcon /> Nova taxa
              </button>
            )}
          </>
        }
      />

      {tab === 'exams' && (
        <ExamListSummaryCards
          total={listQuery.data?.total}
          active={activeCount.data?.total}
          inactive={inactiveCount.data?.total}
          scopeLabel="nos filtros atuais"
        />
      )}

      <div className="attendance-list-page__panel">
        <div className="attendance-list-page__filter-row">
          <div className="attendance-status-tabs" role="tablist" aria-label="Seções">
            {tabs.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                id={`exams-tab-${item.id}`}
                aria-selected={tab === item.id}
                aria-controls="exams-panel"
                className="attendance-status-tabs__tab"
                data-active={tab === item.id}
                onClick={() => setTab(item.id)}
              >
                {item.label}
                {item.count !== undefined ? <b>{item.count}</b> : null}
              </button>
            ))}
          </div>

          {tab === 'exams' && (
            <div className="attendance-list-filters" role="group" aria-label="Filtros">
              <Dropdown
                label="Categoria"
                icon={<TagIcon />}
                options={[
                  { value: '', label: 'Todas' },
                  ...categories.map((category) => ({
                    value: category.id,
                    label: category.name,
                  })),
                ]}
                value={categoryId}
                onChange={change(setCategoryId)}
              />
              <Dropdown
                label="Espécie"
                icon={<PatientsIcon />}
                options={[
                  { value: '', label: 'Todas' },
                  ...species.map((item) => ({
                    value: item.id,
                    label: item.name,
                  })),
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
                <button
                  type="button"
                  className="attendance-list-filters__clear"
                  onClick={clearFilters}
                >
                  <CloseIcon /> Limpar filtros
                </button>
              )}
            </div>
          )}

          {tab === 'clinics' && (
            <div className="attendance-list-filters" role="group" aria-label="Filtros">
              <Dropdown
                label="Clínica"
                icon={<ClinicsIcon />}
                options={[{ value: '', label: 'Todas' }, ...clinicOptions]}
                value={clinicFilter}
                onChange={setClinicFilter}
              />
            </div>
          )}
        </div>

        <div id="exams-panel" role="tabpanel" aria-labelledby={`exams-tab-${tab}`}>
          {tab === 'onCall' && <OnCallFeeSettingsPanel />}
          {tab === 'urgency' && <UrgencyFeePanel />}
          {tab === 'clinics' && (
            <ClinicFeeRulesPanel
              clinicFilter={clinicFilter}
              creating={creatingClinicFee}
              onCreatingChange={setCreatingClinicFee}
            />
          )}
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
              <AttendanceListPagination
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
