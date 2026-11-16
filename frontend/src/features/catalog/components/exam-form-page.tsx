import { useNavigate, useParams } from 'react-router'

import { Button } from '../../../shared/ui/button'
import { PageHeader } from '../../../shared/ui/page-header'
import '../../../shared/ui/button.css'
import { useAuth } from '../../auth/auth-context'
import { useCreateExamMutation } from '../api/use-create-exam-mutation'
import { useExamQuery } from '../api/use-exam-query'
import { useUpdateExamMutation } from '../api/use-update-exam-mutation'
import { ExamForm } from './exam-form'
import '../../attendances/components/attendance-draft-page.css'
import '../../attendances/components/attendance-summary-bar.css'
import './exam-form-page.css'

const FORM_ID = 'exam-form'

interface ExamFormPageProps {
  newPanel?: boolean
}

/** Tela de formulário de exame; `newPanel` abre o cadastro de pacote/perfil. */
export function ExamFormPage({ newPanel = false }: ExamFormPageProps = {}) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { examId } = useParams<{ examId: string }>()
  const isEditing = examId !== undefined

  const examQuery = useExamQuery(examId ?? null)
  const createMutation = useCreateExamMutation()
  const updateMutation = useUpdateExamMutation()

  function goToList() {
    navigate('/cadastros/exames')
  }

  if (isEditing && examQuery.isLoading) {
    return (
      <div className="attendance-draft-page">
        <p className="attendance-draft-page__hint">Carregando…</p>
      </div>
    )
  }

  if (isEditing && !examQuery.data) {
    return (
      <div className="attendance-draft-page">
        <p className="attendance-draft-page__hint">Exame não encontrado.</p>
      </div>
    )
  }

  const exam = isEditing ? (examQuery.data ?? null) : null
  const isPanel = newPanel || (exam?.isPanel ?? false)
  const noun = isPanel ? 'pacote' : 'exame'
  const submitting = isEditing ? updateMutation.isPending : createMutation.isPending
  const submitError = isEditing ? updateMutation.error : createMutation.error

  return (
    <div className="attendance-draft-page">
      <PageHeader title={isEditing ? `Editar ${noun}` : `Novo ${noun}`} />

      <div className="attendance-draft-page__body">
        <ExamForm
          exam={exam}
          submitting={submitting}
          error={submitError}
          formId={FORM_ID}
          hideActions
          panel={newPanel}
          canManagePrice={user?.permissions.includes('pricing.manage') ?? false}
          onCancel={goToList}
          onSubmitCreate={(values) => createMutation.mutate(values, { onSuccess: goToList })}
          onSubmitUpdate={(values) => {
            if (!examId || !exam) return
            updateMutation.mutate(
              {
                id: examId,
                values: { ...values, expectedRowVersion: exam.rowVersion },
              },
              { onSuccess: goToList },
            )
          }}
        />
      </div>

      <div className="attendance-summary-bar" role="region" aria-label={`Ações do ${noun}`}>
        <div className="attendance-summary-bar__actions exam-form-page__actions">
          <Button type="button" variant="cancel" disabled={submitting} onClick={goToList}>
            Cancelar
          </Button>
          <Button type="submit" form={FORM_ID} disabled={submitting}>
            {submitting ? 'Salvando…' : `Salvar ${noun}`}
          </Button>
        </div>
      </div>
    </div>
  )
}
