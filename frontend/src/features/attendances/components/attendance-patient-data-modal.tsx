import { Modal } from '../../../shared/ui/modal'
import { useUpdatePatientMutation } from '../../patients/api/use-update-patient-mutation'
import type { Patient } from '../../patients/api/patients-api'
import { PatientForm } from '../../patients/components/patient-form'

interface AttendancePatientDataModalProps {
  patient: Patient
  onClose: () => void
}

/** Corrige o cadastro do paciente (nome, espécie, idade, tutor…) sem sair do atendimento.
 * Atenção: é o mesmo registro de Pacientes, então vale para todos os atendimentos dele. */
export function AttendancePatientDataModal({ patient, onClose }: AttendancePatientDataModalProps) {
  const mutation = useUpdatePatientMutation()

  return (
    <Modal titleId="patient-data-title" size="lg" onClose={onClose} canDismiss={!mutation.isPending}>
      <h2 id="patient-data-title" className="attendance-correction-block__modal-title">
        Corrigir cadastro do paciente
      </h2>
      <p className="attendance-readonly-detail__hint">
        Esta correção altera o cadastro do paciente em todos os atendimentos dele.
      </p>
      <PatientForm
        patient={patient}
        submitting={mutation.isPending}
        error={mutation.error}
        onCancel={onClose}
        onSubmitUpdate={(values) =>
          mutation.mutate(
            { id: patient.id, values: { ...values, expectedRowVersion: patient.rowVersion } },
            { onSuccess: onClose },
          )
        }
      />
    </Modal>
  )
}
