import { useRef } from 'react'
import { useNavigate, useParams } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { PageHeader } from '../../../shared/ui/page-header'
import { useClinicQuery } from '../api/use-clinic-query'
import { useCreateClinicMutation } from '../api/use-create-clinic-mutation'
import { useUpdateClinicMutation } from '../api/use-update-clinic-mutation'
import { ClinicForm } from './clinic-form'
import './clinic-form-page.css'

const LIST_PATH = '/cadastros/clinicas'

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

  function goToList(selectedId?: string) {
    void navigate(selectedId ? `${LIST_PATH}?clinica=${selectedId}` : LIST_PATH)
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
    return (
      <ClinicForm
        clinic={isEditing ? clinic : null}
        submitting={createMutation.isPending || updateMutation.isPending}
        error={isEditing ? updateMutation.error : createMutation.error}
        onCancel={() => goToList(clinicId)}
        onSubmitCreate={(values) => {
          if (submittingRef.current) return
          submittingRef.current = true
          createMutation.mutate(values, {
            onSuccess: (created) => goToList(created.id),
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
              onSuccess: () => goToList(clinicId),
              onError: () => {
                submittingRef.current = false
              },
            },
          )
        }}
      />
    )
  }

  return (
    <div className="clinic-form-page">
      <PageHeader title={title} />
      <div className="clinic-form-page__body">{renderBody()}</div>
    </div>
  )
}
