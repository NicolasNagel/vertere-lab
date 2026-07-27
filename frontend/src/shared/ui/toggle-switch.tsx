import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react'

import './toggle-switch.css'

interface ToggleSwitchProps extends InputHTMLAttributes<HTMLInputElement> {
  label: ReactNode
  description?: ReactNode
}

// Mesmo padrão de acessibilidade do Checkbox: input nativo escondido
// visualmente (clip, não `display:none`) para reproduzir o pill da
// referência, mas ainda focável/anunciado por leitor de tela. O `<label>`
// engloba texto + descrição para o clique funcionar em toda a linha, mas o
// nome acessível do input fica restrito ao `label` (via `aria-label`) — do
// contrário o rótulo computado juntaria label+descrição num único texto,
// impossível de referenciar isoladamente por `getByLabelText`/leitor de tela.
export const ToggleSwitch = forwardRef<HTMLInputElement, ToggleSwitchProps>(function ToggleSwitch(
  { label, description, className, ...inputProps },
  ref,
) {
  const descriptionId = useId()

  return (
    <label className={`toggle-switch ${className ?? ''}`.trim()}>
      <span className="toggle-switch__text">
        <span className="toggle-switch__label">{label}</span>
        {description && (
          <span id={descriptionId} className="toggle-switch__description">
            {description}
          </span>
        )}
      </span>
      <input
        ref={ref}
        type="checkbox"
        className="toggle-switch__input"
        aria-label={typeof label === 'string' ? label : undefined}
        aria-describedby={description ? descriptionId : undefined}
        {...inputProps}
      />
      <span className="toggle-switch__track" aria-hidden="true">
        <span className="toggle-switch__thumb" />
      </span>
    </label>
  )
})
