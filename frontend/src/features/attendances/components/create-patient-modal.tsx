import { useSubmitGuard } from '../../../shared/lib/use-submit-guard'
import { Modal } from '../../../shared/ui/modal'
import { useCreatePatientMutation } from '../../patients/api/use-create-patient-mutation'
import { PatientForm } from '../../patients/components/patient-form'
import type { Patient } from '../../patients/api/patients-api'
import './create-patient-modal.css'

interface CreatePatientModalProps {
  initialName: string
  onCreated: (patient: Patient) => void
  onClose: () => void
}

/** Aberto de dentro do formulário de novo atendimento — o estado já
 * preenchido do atendimento (clínica/veterinário/observações) continua
 * montado por trás, nunca é perdido (`.claude/rules/12-attendance.md`:
 * "criação rápida de cadastro não perde o rascunho").
 *
 * `PatientForm` decide criar vs. editar pela presença do prop `patient`
 * (verdadeiro = editar) — por isso passamos `patient={null}` aqui, mesmo
 * tendo um nome digitado na busca; não há como pré-preencher só o nome
 * sem entrar no fluxo de edição, então o usuário digita de novo. Simples e
 * correto > reaproveitar o componente de forma que o quebra.
 */
export function CreatePatientModal({ initialName, onCreated, onClose }: CreatePatientModalProps) {
  const createMutation = useCreatePatientMutation()
  const guardCreate = useSubmitGuard()

  return (
    <Modal
      titleId="create-patient-modal-title"
      size="lg"
      className="create-patient-modal"
      canDismiss={!createMutation.isPending}
      onClose={onClose}
    >
        <h2 id="create-patient-modal-title" className="create-patient-modal__title">
          Novo paciente
        </h2>
        {initialName && (
          <p className="create-patient-modal__hint">Buscado como “{initialName}”.</p>
        )}
        <PatientForm
          patient={null}
          submitting={createMutation.isPending}
          error={createMutation.error}
          onCancel={onClose}
          onSubmitCreate={(values) => {
            guardCreate((release) =>
              createMutation.mutate(values, { onSuccess: onCreated, onSettled: release }),
            )
          }}
        />
    </Modal>
  )
}
