import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'

import './checkbox.css'

interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {
  label: ReactNode
}

// O `<input>` nativo fica visualmente escondido (clip, não `display:none`) só
// para reproduzir o quadrado customizado da referência — continua focável
// pelo teclado e anunciado por leitor de tela; o quadrado visual é decorativo
// (`aria-hidden`) e reage ao estado `:checked` do input via CSS.
export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, className, ...inputProps },
  ref,
) {
  return (
    <label className={`checkbox ${className ?? ''}`.trim()}>
      <input ref={ref} type="checkbox" className="checkbox__input" {...inputProps} />
      <span className="checkbox__box" aria-hidden="true">
        <svg
          className="checkbox__check"
          width="8"
          height="8"
          viewBox="0 0 10 10"
          fill="none"
        >
          <path d="M1 5l3 3 5-6" stroke="#fff" strokeWidth={1.6} />
        </svg>
      </span>
      <span className="checkbox__label">{label}</span>
    </label>
  )
})
