import { useState } from 'react'

import { useAuth } from '../../auth/auth-provider'
import { Button } from '../../../shared/ui/button'
import { PlusIcon } from '../../../shared/ui/icons'
import { useCreateExamMutation } from '../api/use-create-exam-mutation'
import { useDeactivateExamMutation } from '../api/use-deactivate-exam-mutation'
import { useExamQuery } from '../api/use-exam-query'
import { useExamsQuery } from '../api/use-exams-query'
import { useUpdateExamMutation } from '../api/use-update-exam-mutation'
import { ExamDetail } from './exam-detail'
import { ExamForm } from './exam-form'
import { ExamList } from './exam-list'
import './exams-page.css'

type PanelMode = 'view' | 'create' | 'edit'

export function ExamsPage() {
  const { user } = useAuth()
  const canManage = user?.permissions.includes('catalog.manage') ?? false

  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<PanelMode>('view')

  const listQuery = useExamsQuery({ search: search || undefined, pageSize: 100 })
  const detailQuery = useExamQuery(mode === 'create' ? null : selectedId)

  const createMutation = useCreateExamMutation()
  const updateMutation = useUpdateExamMutation()
  const deactivateMutation = useDeactivateExamMutation()

  const exams = listQuery.data?.items ?? []
  const activeCount = exams.filter((exam) => exam.status === 'ACTIVE').length

  function handleSelect(id: string) {
    setSelectedId(id)
    setMode('view')
  }

  function handleStartCreate() {
    setSelectedId(null)
    setMode('create')
  }

  function handleDeactivate() {
    if (!selectedId) return
    deactivateMutation.mutate(selectedId)
  }

  return (
    <div className="exams-page">
      <div className="exams-page__header">
        <div>
          <div className="exams-page__eyebrow">Cadastros</div>
          <h1 className="exams-page__title">Exames &amp; Preços</h1>
        </div>
        {canManage && (
          <Button type="button" className="exams-page__new-button" onClick={handleStartCreate}>
            <PlusIcon /> Novo exame
          </Button>
        )}
      </div>

      <div className="exams-page__body">
        <ExamList
          exams={exams}
          activeCount={activeCount}
          selectedId={mode === 'create' ? null : selectedId}
          search={search}
          isLoading={listQuery.isLoading}
          onSearchChange={setSearch}
          onSelect={handleSelect}
        />

        {mode === 'create' ? (
          <div className="exams-page__create-panel">
            <h2 className="exams-page__create-title">Novo exame</h2>
            <ExamForm
              exam={null}
              submitting={createMutation.isPending}
              error={createMutation.error}
              onCancel={() => setMode('view')}
              onSubmitCreate={(values) =>
                createMutation.mutate(values, {
                  onSuccess: (exam) => {
                    setSelectedId(exam.id)
                    setMode('view')
                  },
                })
              }
            />
          </div>
        ) : (
          <ExamDetail
            exam={detailQuery.data ?? null}
            isLoading={selectedId !== null && detailQuery.isLoading}
            isEditing={mode === 'edit'}
            canManage={canManage}
            submitting={updateMutation.isPending}
            submitError={updateMutation.error}
            onStartEdit={() => setMode('edit')}
            onCancelEdit={() => setMode('view')}
            onSubmitUpdate={(values) => {
              if (!selectedId || !detailQuery.data) return
              updateMutation.mutate(
                {
                  id: selectedId,
                  values: { ...values, expectedRowVersion: detailQuery.data.rowVersion },
                },
                { onSuccess: () => setMode('view') },
              )
            }}
            onDeactivate={handleDeactivate}
          />
        )}
      </div>
    </div>
  )
}
