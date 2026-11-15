import type { ButtonHTMLAttributes } from 'react'

import './button.css'

/**
 * - primary: ação principal da área (no máximo uma por área).
 * - secondary: ações neutras (Editar, Voltar).
 * - cancel: qualquer "Cancelar"/"Descartar"; neutro, vermelho ao passar o mouse.
 * - danger: botão final de ação destrutiva, só em modal de confirmação.
 * - ghost: baixa ênfase, dentro de texto.
 */
export type ButtonVariant = 'primary' | 'secondary' | 'cancel' | 'danger' | 'ghost'
export type ButtonSize = 'md' | 'sm'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

export function Button({ variant = 'primary', size = 'md', className, ...rest }: ButtonProps) {
  const sizeClass = size === 'sm' ? ' button--sm' : ''
  return (
    <button className={`button button--${variant}${sizeClass} ${className ?? ''}`.trim()} {...rest} />
  )
}
