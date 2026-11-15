import { useRef } from 'react'
import { useNavigate } from 'react-router'

import { Button } from '../../../shared/ui/button'
import { PageHeader } from '../../../shared/ui/page-header'
import { useAuth } from '../../auth/auth-context'
import { useCreateVeterinarianMutation } from '../api/use-create-veterinarian-mutation'
import { VeterinarianForm } from './veterinarian-form'
import '../../attendances/components/attendance-draft-page.css'
import '../../attendances/components/attendance-summary-bar.css'
import './veterinarian-form-page.css'

const LIST_PATH = '/cadastros/veterinarios'
const FORM_ID = 'veterinarian-form'

/** Novo veterinário (`/cadastros/veterinarios/novo`), no layout do Novo Protocolo. */
export function VeterinarianFormPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.permissions.includes('veterinarians.manage') ?? false
  const createMutation = useCreateVeterinarianMutation()
  // Impede um segundo envio (duplo clique) antes de o estado de "salvando" chegar à tela.
  const submittingRef = useRef(false)

  function goToList() {
    void navigate(LIST_PATH)
  }

  return (
    <div className="attendance-draft-page">
      <PageHeader title="Novo veterinário" />
      <div className="attendance-draft-page__body">
        {canManage ? (
          <VeterinarianForm
            formId={FORM_ID}
            submitting={createMutation.isPending}
            error={createMutation.error}
            onSubmitCreate={(values, clinicIds, primaryClinicId) => {
              if (submittingRef.current) return
              submittingRef.current = true
              createMutation.mutate(
                { values, clinicIds, primaryClinicId },
                {
                  onSuccess: goToList,
                  onError: () => {
                    submittingRef.current = false
                  },
                },
              )
            }}
          />
        ) : (
          <p className="attendance-draft-page__hint">
            Você não tem permissão para gerenciar veterinários.
          </p>
        )}
      </div>
      {canManage && (
        <div className="attendance-summary-bar" role="region" aria-label="Ações do veterinário">
          <div className="attendance-summary-bar__actions veterinarian-form-page__actions">
            <Button
              type="button"
              variant="cancel"
              disabled={createMutation.isPending}
              onClick={goToList}
            >
              Cancelar
            </Button>
            <Button type="submit" form={FORM_ID} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Salvando…' : 'Salvar'}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
