import { useRef } from 'react'
import { useNavigate, useParams } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { Button } from '../../../shared/ui/button'

import { useAuth } from '../../auth/auth-context'
import { PageHeader } from '../../../shared/ui/page-header'
import { useClinicQuery } from '../api/use-clinic-query'
import { useCreateClinicMutation } from '../api/use-create-clinic-mutation'
import { useUpdateClinicMutation } from '../api/use-update-clinic-mutation'
import { ClinicForm } from './clinic-form'
import '../../attendances/components/attendance-draft-page.css'
import '../../attendances/components/attendance-summary-bar.css'
import './clinic-form-page.css'

const LIST_PATH = '/cadastros/clinicas'
const FORM_ID = 'clinic-form'

/** Tela de cadastro: `/cadastros/clinicas/nova` (criar) e `/:clinicId/editar` (editar). */
export function ClinicFormPage() {
  const { clinicId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.permissions.includes('clinics.manage') ?? false

  const detailQuery = useClinicQuery(clinicId ?? null)
  const createMutation = useCreateClinicMutation()
  const updateMutation = useUpdateClinicMutation()

  // Impede um segundo envio (duplo clique) antes de o estado de "salvando" chegar à tela.
  const submittingRef = useRef(false)

  const isEditing = clinicId !== undefined
  const title = isEditing ? 'Editar clínica' : 'Nova clínica'

  // Volta sempre para a lista limpa: o detalhe só abre quando o usuário clica numa linha.
  function goToList() {
    void navigate(LIST_PATH)
  }

  function renderBody() {
    if (!canManage) {
      return (
        <p className="clinic-form-page__notice">Você não tem permissão para gerenciar clínicas.</p>
      )
    }
    if (isEditing && detailQuery.isLoading) {
      return <p className="clinic-form-page__notice">Carregando…</p>
    }
    if (isEditing && !detailQuery.data) {
      return <p className="clinic-form-page__notice">Clínica não encontrada.</p>
    }
    const clinic = detailQuery.data ?? null
    const isConflict =
      updateMutation.error instanceof ApiError && updateMutation.error.status === 409
    return (
      <>
        {isEditing && isConflict && (
          <div className="clinic-form-page__conflict" role="status">
            <span>Os dados desta clínica mudaram desde que você abriu a tela.</span>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                updateMutation.reset()
                submittingRef.current = false
                void detailQuery.refetch()
              }}
            >
              Recarregar dados
            </Button>
          </div>
        )}
        <ClinicForm
          key={clinic?.rowVersion ?? 'new'}
          formId={FORM_ID}
          hideActions
          clinic={isEditing ? clinic : null}
          submitting={createMutation.isPending || updateMutation.isPending}
          error={isEditing ? updateMutation.error : createMutation.error}
          onCancel={goToList}
          onSubmitCreate={(values) => {
            if (submittingRef.current) return
            submittingRef.current = true
            createMutation.mutate(values, {
              onSuccess: goToList,
              onError: () => {
                submittingRef.current = false
              },
            })
          }}
          onSubmitUpdate={(values) => {
            if (!clinicId || !clinic || submittingRef.current) return
            submittingRef.current = true
            updateMutation.mutate(
              { id: clinicId, values: { ...values, expectedRowVersion: clinic.rowVersion } },
              {
                onSuccess: goToList,
                onError: () => {
                  submittingRef.current = false
                },
              },
            )
          }}
        />
      </>
    )
  }

  return (
    <div className="attendance-draft-page">
      <PageHeader title={title} />
      <div className="attendance-draft-page__body">{renderBody()}</div>
      {canManage && (
        <div className="attendance-summary-bar" role="region" aria-label="Ações da clínica">
          <div className="attendance-summary-bar__actions clinic-form-page__actions">
            <Button
              type="button"
              variant="cancel"
              disabled={createMutation.isPending || updateMutation.isPending}
              onClick={goToList}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              form={FORM_ID}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {createMutation.isPending || updateMutation.isPending ? 'Salvando…' : 'Salvar'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
