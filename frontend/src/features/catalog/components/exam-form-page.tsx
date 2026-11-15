import { Link, useNavigate, useParams } from 'react-router'

import { Button } from '../../../shared/ui/button'
import { ArrowLeftIcon } from '../../../shared/ui/icons'
import { PageHeader } from '../../../shared/ui/page-header'
import '../../../shared/ui/button.css'
import { useAuth } from '../../auth/auth-context'
import { useCreateExamMutation } from '../api/use-create-exam-mutation'
import { useExamQuery } from '../api/use-exam-query'
import { useUpdateExamMutation } from '../api/use-update-exam-mutation'
import { ExamForm } from './exam-form'
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
      <div className="exam-form-page">
        <p className="exam-form-page__empty">Carregando…</p>
      </div>
    )
  }

  if (isEditing && !examQuery.data) {
    return (
      <div className="exam-form-page">
        <p className="exam-form-page__empty">Exame não encontrado.</p>
      </div>
    )
  }

  const exam = isEditing ? (examQuery.data ?? null) : null
  const isPanel = newPanel || (exam?.isPanel ?? false)
  const noun = isPanel ? 'pacote' : 'exame'
  const submitting = isEditing ? updateMutation.isPending : createMutation.isPending
  const submitError = isEditing ? updateMutation.error : createMutation.error

  return (
    <div className="exam-form-page">
      <PageHeader
        title={isEditing ? `Editar ${noun}` : `Novo ${noun}`}
        actions={
          <>
            <Link to="/cadastros/exames" className="button button--secondary">
              <ArrowLeftIcon />
              Voltar
            </Link>
            <Button type="submit" form={FORM_ID} disabled={submitting}>
              {submitting ? 'Salvando…' : `Salvar ${noun}`}
            </Button>
          </>
        }
      />

      <div className="exam-form-page__body">
        <ExamForm
          exam={exam}
          submitting={submitting}
          error={submitError}
          formId={FORM_ID}
          hideActions
          panel={newPanel}
          canManagePrice={user?.permissions.includes('pricing.manage') ?? false}
          onCancel={goToList}
          onSubmitCreate={(values) =>
            createMutation.mutate(values, { onSuccess: goToList })
          }
          onSubmitUpdate={(values) => {
            if (!examId || !exam) return
            updateMutation.mutate(
              { id: examId, values: { ...values, expectedRowVersion: exam.rowVersion } },
              { onSuccess: goToList },
            )
          }}
        />
      </div>
    </div>
  )
}
