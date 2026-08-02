import { forwardRef, type ReactNode, type SelectHTMLAttributes } from 'react'

import './select.css'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  options: SelectOption[]
  errorMessage?: string
  leadingIcon?: ReactNode
}

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, options, errorMessage, leadingIcon, id, className, ...selectProps },
  ref,
) {
  const errorId = errorMessage ? `${id}-error` : undefined

  return (
    <div className={`select-field ${className ?? ''}`.trim()}>
      <label className="select-field__label" htmlFor={id}>
        {label}
      </label>
      <div className="select-field__control" data-invalid={Boolean(errorMessage)}>
        {leadingIcon && <span className="select-field__leading-icon">{leadingIcon}</span>}
        <select
          ref={ref}
          id={id}
          className={`select-field__input${leadingIcon ? ' select-field__input--with-icon' : ''}`}
          aria-invalid={errorMessage ? 'true' : undefined}
          aria-describedby={errorId}
          {...selectProps}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      {errorMessage && (
        <span id={errorId} role="alert" className="select-field__error">
          {errorMessage}
        </span>
      )}
    </div>
  )
})
