import { useNavigate } from 'react-router'

import { useSubmitGuard } from '../../../shared/lib/use-submit-guard'
import { Button } from '../../../shared/ui/button'
import { PageHeader } from '../../../shared/ui/page-header'
import { useAuth } from '../../auth/auth-context'
import { useCreatePatientMutation } from '../api/use-create-patient-mutation'
import { PatientCreateForm } from './patient-create-form'
import '../../attendances/components/attendance-draft-page.css'
import '../../attendances/components/attendance-summary-bar.css'
import './patient-form-page.css'

const LIST_PATH = '/pacientes'
const FORM_ID = 'patient-form'

/** Novo paciente (`/pacientes/novo`), no layout do Novo Protocolo. */
export function PatientFormPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.permissions.includes('patients.manage') ?? false
  const createMutation = useCreatePatientMutation()
  const guardCreate = useSubmitGuard()

  return (
    <div className="attendance-draft-page">
      <PageHeader title="Novo paciente" />
      <div className="attendance-draft-page__body">
        {canManage ? (
          <PatientCreateForm
            formId={FORM_ID}
            submitting={createMutation.isPending}
            error={createMutation.error}
            onSubmitCreate={(values) =>
              guardCreate((release) =>
                createMutation.mutate(values, {
                  onSuccess: (patient) => navigate(`/pacientes/${patient.id}`),
                  onSettled: release,
                }),
              )
            }
          />
        ) : (
          <p role="alert" className="attendance-draft-page__hint">
            Você não tem permissão para cadastrar pacientes.
          </p>
        )}
      </div>
      {canManage && (
        <div className="attendance-summary-bar" role="region" aria-label="Ações do paciente">
          <div className="attendance-summary-bar__actions patient-form-page__actions">
            <Button
              type="button"
              variant="cancel"
              disabled={createMutation.isPending}
              onClick={() => navigate(LIST_PATH)}
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
