import { forwardRef, useId, useState } from 'react'

import { LockIcon } from './icons'
import { TextField, type TextFieldProps } from './text-field'
import './password-field.css'

type PasswordFieldProps = Omit<TextFieldProps, 'type' | 'icon' | 'endAdornment'>

export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  function PasswordField(props, ref) {
    const [visible, setVisible] = useState(false)
    const toggleId = useId()

    return (
      <TextField
        ref={ref}
        type={visible ? 'text' : 'password'}
        icon={<LockIcon />}
        endAdornment={
          <button
            type="button"
            id={toggleId}
            className="password-field__toggle"
            onClick={() => setVisible((current) => !current)}
            aria-label={visible ? 'Ocultar senha' : 'Mostrar senha'}
          >
            {visible ? 'ocultar' : 'mostrar'}
          </button>
        }
        {...props}
      />
    )
  },
)
