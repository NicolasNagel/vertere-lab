import { useState } from 'react'
import { useNavigate } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { Button } from '../../../shared/ui/button'
import { PlusIcon } from '../../../shared/ui/icons'
import { Pagination } from '../../../shared/ui/pagination'
import { SelectField } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import type { ExamStatus } from '../api/catalog-api'
import { useActiveExamCategoriesQuery } from '../api/use-active-exam-categories-query'
import { useDeactivateExamMutation } from '../api/use-deactivate-exam-mutation'
import { useExamsQuery } from '../api/use-exams-query'
import { ExamImportButton } from './exam-import-button'
import { ExamTable } from './exam-table'
import { OnCallFeeSettingsPanel } from './on-call-fee-settings-panel'
import './exams-page.css'

type Tab = 'exams' | 'fees'

const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'ACTIVE', label: 'Ativos' },
  { value: 'INACTIVE', label: 'Inativos' },
]

export function ExamsPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.permissions.includes('catalog.manage') ?? false
  const priceVisible = user?.permissions.includes('pricing.read') ?? false

  const [tab, setTab] = useState<Tab>('exams')
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [speciesId, setSpeciesId] = useState('')
  const [status, setStatus] = useState<ExamStatus | ''>('')
  const [page, setPage] = useState(1)

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

  function resetPageAnd<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value)
      setPage(1)
    }
  }

  return (
    <div className="exams-page">
      <div className="exams-page__header">
        <div>
          <div className="exams-page__eyebrow">Cadastros</div>
          <h1 className="exams-page__title">Exames &amp; Preços</h1>
        </div>
        {canManage && tab === 'exams' && (
          <div className="exams-page__header-actions">
            <ExamImportButton />
            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate('/cadastros/exames/novo-pacote')}
            >
              <PlusIcon /> Novo pacote
            </Button>
            <Button type="button" onClick={() => navigate('/cadastros/exames/novo')}>
              <PlusIcon /> Novo exame
            </Button>
          </div>
        )}
      </div>

      <div className="exams-page__tabs" role="tablist" aria-label="Seções">
        <button
          type="button"
          role="tab"
          id="exams-tab-exams"
          aria-selected={tab === 'exams'}
          aria-controls="exams-panel"
          onClick={() => setTab('exams')}
        >
          Exames
        </button>
        <button
          type="button"
          role="tab"
          id="exams-tab-fees"
          aria-selected={tab === 'fees'}
          aria-controls="exams-panel"
          onClick={() => setTab('fees')}
        >
          Taxas de plantão
        </button>
      </div>

      <div
        className="exams-page__main"
        id="exams-panel"
        role="tabpanel"
        aria-labelledby={tab === 'exams' ? 'exams-tab-exams' : 'exams-tab-fees'}
      >
        {tab === 'fees' && <OnCallFeeSettingsPanel />}
        {tab === 'exams' && (
          <>
            <div className="exams-page__filters">
              <TextField
                id="exams-search"
                type="search"
                label="Buscar exame"
                placeholder="Nome ou código"
                value={search}
                onChange={(event) => resetPageAnd(setSearch)(event.target.value)}
              />
              <SelectField
                id="exams-category"
                label="Categoria"
                value={categoryId}
                options={[
                  { value: '', label: 'Todas' },
                  ...categories.map((category) => ({ value: category.id, label: category.name })),
                ]}
                onChange={(event) => resetPageAnd(setCategoryId)(event.target.value)}
              />
              <SelectField
                id="exams-species"
                label="Espécie"
                value={speciesId}
                options={[
                  { value: '', label: 'Todas' },
                  ...species.map((item) => ({ value: item.id, label: item.name })),
                ]}
                onChange={(event) => resetPageAnd(setSpeciesId)(event.target.value)}
              />
              <SelectField
                id="exams-status"
                label="Status"
                value={status}
                options={STATUS_OPTIONS}
                onChange={(event) => resetPageAnd(setStatus)(event.target.value as ExamStatus | '')}
              />
            </div>
            <ExamTable
              exams={listQuery.data?.items ?? []}
              categories={categories}
              species={species}
              isLoading={listQuery.isLoading}
              isError={listQuery.isError}
              canManage={canManage}
              priceVisible={priceVisible}
              onRowClick={(examId) => navigate(`/cadastros/exames/${examId}`)}
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
  )
}
