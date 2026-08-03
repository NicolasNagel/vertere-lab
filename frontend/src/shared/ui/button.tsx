import type { ButtonHTMLAttributes } from 'react'

import './button.css'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
}

export function Button({ variant = 'primary', className, ...rest }: ButtonProps) {
  return <button className={`button button--${variant} ${className ?? ''}`.trim()} {...rest} />
}
