import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'

import './text-field.css'

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  errorMessage?: string
  icon?: ReactNode
  endAdornment?: ReactNode
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, errorMessage, icon, endAdornment, id, className, ...inputProps },
  ref,
) {
  const errorId = errorMessage ? `${id}-error` : undefined

  return (
    <div className={`text-field ${className ?? ''}`.trim()}>
      <label className="text-field__label" htmlFor={id}>
        {label}
      </label>
      <div className="text-field__control" data-invalid={Boolean(errorMessage)}>
        {icon && <span className="text-field__icon">{icon}</span>}
        <input
          ref={ref}
          id={id}
          className="text-field__input"
          aria-invalid={errorMessage ? 'true' : undefined}
          aria-describedby={errorId}
          {...inputProps}
        />
        {endAdornment && <span className="text-field__end-adornment">{endAdornment}</span>}
      </div>
      {errorMessage && (
        <span id={errorId} role="alert" className="text-field__error">
          {errorMessage}
        </span>
      )}
    </div>
  )
})
