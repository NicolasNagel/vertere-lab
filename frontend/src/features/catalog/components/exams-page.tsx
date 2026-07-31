import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { Button } from '../../../shared/ui/button'
import { PlusIcon } from '../../../shared/ui/icons'
import { Pagination } from '../../../shared/ui/pagination'
import { useActiveExamCategoriesQuery } from '../api/use-active-exam-categories-query'
import { useDeactivateExamMutation } from '../api/use-deactivate-exam-mutation'
import { useExamsQuery } from '../api/use-exams-query'
import { ExamCatalogSidebar } from './exam-catalog-sidebar'
import { ExamImportButton } from './exam-import-button'
import { ExamStatCards } from './exam-stat-cards'
import { ExamTable } from './exam-table'
import './exams-page.css'

export function ExamsPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.permissions.includes('catalog.manage') ?? false
  const priceVisible = user?.permissions.includes('pricing.read') ?? false

  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState<string | null>(null)
  const [speciesId, setSpeciesId] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  // Página inteira cabe em 100 itens hoje (ver pendência documentada no
  // plano) — contagens por categoria/espécie e filtro refletem essa página
  // carregada, não uma agregação de servidor.
  const listQuery = useExamsQuery({
    search: search || undefined,
    categoryId: categoryId ?? undefined,
    speciesId: speciesId ?? undefined,
    page,
    pageSize: 25,
  })
  const categoriesQuery = useActiveExamCategoriesQuery()
  const speciesQuery = useSpeciesQuery()
  const deactivateMutation = useDeactivateExamMutation()

  const examItems = listQuery.data?.items
  const categories = categoriesQuery.data ?? []
  const species = speciesQuery.data ?? []

  const allExams = useMemo(() => examItems ?? [], [examItems])

  const filteredExams = useMemo(
    () =>
      allExams.filter(
        (exam) =>
          (categoryId === null || exam.categoryId === categoryId) &&
          (speciesId === null || exam.speciesIds.includes(speciesId)),
      ),
    [allExams, categoryId, speciesId],
  )

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const exam of allExams) {
      counts.set(exam.categoryId, (counts.get(exam.categoryId) ?? 0) + 1)
    }
    return counts
  }, [allExams])

  const activeCount = allExams.filter((exam) => exam.status === 'ACTIVE').length

  // KPI de exibição, não valor financeiro persistido/cobrado — aproximação
  // simples para o card "Ticket médio", não um cálculo de fechamento. Só
  // considera exames ativos, mesma população do card "Exames ativos" ao
  // lado — um exame inativado não deve puxar a média do catálogo vigente.
  const pricedExams = allExams.filter(
    (exam) => exam.status === 'ACTIVE' && exam.priceBase !== null,
  )
  const averagePriceLabel =
    pricedExams.length > 0
      ? `R$ ${(
          pricedExams.reduce((sum, exam) => sum + Number(exam.priceBase), 0) / pricedExams.length
        )
          .toFixed(2)
          .replace('.', ',')}`
      : null

  const lastUpdatedAt = allExams.reduce<string | null>(
    (latest, exam) => (latest === null || exam.updatedAt > latest ? exam.updatedAt : latest),
    null,
  )

  return (
    <div className="exams-page">
      <div className="exams-page__header">
        <div>
          <div className="exams-page__eyebrow">Cadastros</div>
          <h1 className="exams-page__title">Exames &amp; Preços</h1>
        </div>
        {canManage && (
          <div className="exams-page__header-actions">
            <ExamImportButton />
            <Button
              type="button"
              className="exams-page__new-button"
              onClick={() => navigate('/cadastros/exames/novo')}
            >
              <PlusIcon /> Novo exame
            </Button>
          </div>
        )}
      </div>

      <div className="exams-page__body">
        <ExamCatalogSidebar
          categories={categories}
          categoryCounts={categoryCounts}
          totalCount={allExams.length}
          selectedCategoryId={categoryId}
          onSelectCategory={(value) => {
            setCategoryId(value)
            setPage(1)
          }}
          species={species}
          selectedSpeciesId={speciesId}
          onSelectSpecies={(value) => {
            setSpeciesId(value)
            setPage(1)
          }}
        />

        <div className="exams-page__main">
          <ExamStatCards
            activeCount={activeCount}
            averagePriceLabel={averagePriceLabel}
            priceVisible={priceVisible}
            lastUpdatedAt={lastUpdatedAt}
          />
          <ExamTable
            exams={filteredExams}
            categories={categories}
            species={species}
            isLoading={listQuery.isLoading}
            canManage={canManage}
            priceVisible={priceVisible}
            search={search}
            onSearchChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            onRowClick={(examId) => navigate(`/cadastros/exames/${examId}/editar`)}
            onDeactivate={(examId) => deactivateMutation.mutate(examId)}
          />
          <Pagination
            itemLabel={['exame', 'exames']}
            page={listQuery.data?.page ?? page}
            pageSize={listQuery.data?.pageSize ?? 25}
            total={listQuery.data?.total ?? 0}
            onPageChange={setPage}
          />
        </div>
      </div>
    </div>
  )
}
