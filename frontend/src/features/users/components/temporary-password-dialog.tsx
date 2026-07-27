import { Button } from '../../../shared/ui/button'
import type { CreatedUser } from '../api/users-api'
import './temporary-password-dialog.css'

interface TemporaryPasswordDialogProps {
  createdUser: CreatedUser
  onClose: () => void
}

export function TemporaryPasswordDialog({ createdUser, onClose }: TemporaryPasswordDialogProps) {
  return (
    <div className="temporary-password-dialog__backdrop" role="presentation">
      <div
        className="temporary-password-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="temporary-password-dialog-title"
      >
        <h2 id="temporary-password-dialog-title" className="temporary-password-dialog__title">
          Usuário criado
        </h2>
        <p className="temporary-password-dialog__description">
          Compartilhe esta senha temporária com <strong>{createdUser.user.fullName}</strong> (
          {createdUser.user.email}). Ela não será mostrada novamente — o usuário deve trocá-la no
          primeiro acesso.
        </p>
        <p className="temporary-password-dialog__password">{createdUser.temporaryPassword}</p>
        <div className="temporary-password-dialog__actions">
          <Button type="button" autoFocus onClick={onClose}>
            Fechar
          </Button>
        </div>
      </div>
    </div>
  )
}
