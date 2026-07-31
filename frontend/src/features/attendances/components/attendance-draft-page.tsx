import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../auth/auth-context'
import { AttendanceDraftForm } from './attendance-draft-form'
import './attendance-draft-page.css'

export function AttendanceDraftPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const canCreate = user?.permissions.includes('attendances.create') ?? false

  return (
    <div className="attendance-draft-page">
      <div className="attendance-draft-page__header">
        <div>
          <div className="attendance-draft-page__eyebrow">Operação · Novo atendimento</div>
          <h1 className="attendance-draft-page__title">Abertura de rascunho</h1>
        </div>
      </div>

      <div className="attendance-draft-page__body">
        {!canCreate ? (
          <p className="attendance-draft-page__forbidden">
            Você não tem permissão para criar atendimentos.
          </p>
        ) : (
          <AttendanceDraftForm
            onCreated={() => navigate('/operacao')}
            onCancel={() => navigate('/operacao')}
          />
        )}
      </div>
    </div>
  )
}
