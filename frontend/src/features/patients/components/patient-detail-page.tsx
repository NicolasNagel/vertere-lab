import { useState } from 'react'
import { Link, useParams } from 'react-router'

import { useAuth } from '../../auth/auth-context'
import { PageHeader } from '../../../shared/ui/page-header'
import { useDeactivatePatientMutation } from '../api/use-deactivate-patient-mutation'
import { usePatientQuery } from '../api/use-patient-query'
import { useReactivatePatientMutation } from '../api/use-reactivate-patient-mutation'
import { useUpdatePatientMutation } from '../api/use-update-patient-mutation'
import { PatientDetail } from './patient-detail'
import { patientLoadErrorMessage } from './patient-labels'
import '../../../shared/ui/button.css'
import './patient-pages.css'

/** `/pacientes/:patientId`. Reaproveita o detalhe/edição atual até o redesenho em blocos. */
export function PatientDetailPage() {
  const { patientId } = useParams()
  const { user } = useAuth()
  const canManage = user?.permissions.includes('patients.manage') ?? false

  const [isEditing, setIsEditing] = useState(false)
  const detailQuery = usePatientQuery(patientId ?? null)
  const updateMutation = useUpdatePatientMutation()
  const deactivateMutation = useDeactivatePatientMutation()
  const reactivateMutation = useReactivatePatientMutation()

  const patient = detailQuery.data ?? null

  return (
    <div className="patient-page">
      <PageHeader
        title="Paciente"
        actions={
          <Link to="/pacientes" className="button button--secondary">
            Voltar para pacientes
          </Link>
        }
      />
      {detailQuery.isError ? (
        <p role="alert" className="patient-page__message">
          {patientLoadErrorMessage(detailQuery.error)}
        </p>
      ) : (
        <PatientDetail
          patient={patient}
          isLoading={detailQuery.isLoading}
          isEditing={isEditing}
          canManage={canManage}
          submitting={updateMutation.isPending}
          submitError={updateMutation.error}
          onStartEdit={() => setIsEditing(true)}
          onCancelEdit={() => setIsEditing(false)}
          onSubmitUpdate={(values) => {
            if (!patient) return
            updateMutation.mutate(
              { id: patient.id, values: { ...values, expectedRowVersion: patient.rowVersion } },
              { onSuccess: () => setIsEditing(false) },
            )
          }}
          onDeactivate={() => patient && deactivateMutation.mutate(patient.id)}
          onReactivate={() => patient && reactivateMutation.mutate(patient.id)}
        />
      )}
    </div>
  )
}
