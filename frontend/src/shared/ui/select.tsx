import { forwardRef, type SelectHTMLAttributes } from 'react'

import './select.css'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  options: SelectOption[]
  errorMessage?: string
}

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, options, errorMessage, id, className, ...selectProps },
  ref,
) {
  const errorId = errorMessage ? `${id}-error` : undefined

  return (
    <div className={`select-field ${className ?? ''}`.trim()}>
      <label className="select-field__label" htmlFor={id}>
        {label}
      </label>
      <div className="select-field__control" data-invalid={Boolean(errorMessage)}>
        <select
          ref={ref}
          id={id}
          className="select-field__input"
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
