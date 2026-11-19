import { Link, useNavigate } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { useSubmitGuard } from '../../../shared/lib/use-submit-guard'
import { PageHeader } from '../../../shared/ui/page-header'
import { useCreatePatientMutation } from '../api/use-create-patient-mutation'
import { PatientForm } from './patient-form'
import '../../../shared/ui/button.css'
import './patient-pages.css'

/** `/pacientes/novo`. Reaproveita o formulário atual até o redesenho no layout do Novo Protocolo. */
export function PatientFormPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.permissions.includes('patients.manage') ?? false
  const createMutation = useCreatePatientMutation()
  const guardCreate = useSubmitGuard()

  return (
    <div className="patient-page">
      <PageHeader
        title="Novo paciente"
        actions={
          <Link to="/pacientes" className="button button--secondary">
            Voltar para pacientes
          </Link>
        }
      />
      {canManage ? (
        <div className="patient-page__form">
          <PatientForm
            patient={null}
            submitting={createMutation.isPending}
            error={createMutation.error}
            onCancel={() => navigate('/pacientes')}
            onSubmitCreate={(values) =>
              guardCreate((release) =>
                createMutation.mutate(values, {
                  onSuccess: (patient) => navigate(`/pacientes/${patient.id}`),
                  onSettled: release,
                }),
              )
            }
          />
        </div>
      ) : (
        <p role="alert" className="patient-page__message">
          Você não tem permissão para cadastrar pacientes.
        </p>
      )}
    </div>
  )
}
