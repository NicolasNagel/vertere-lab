import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import { Button } from './button'

test('aplica variante e tamanho como classes do componente padrão', () => {
  render(
    <>
      <Button variant="cancel">Cancelar</Button>
      <Button variant="danger" size="sm">
        Cancelar atendimento
      </Button>
      <Button>Salvar</Button>
    </>,
  )

  expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveClass('button', 'button--cancel')
  const danger = screen.getByRole('button', { name: 'Cancelar atendimento' })
  expect(danger).toHaveClass('button--danger', 'button--sm')
  expect(screen.getByRole('button', { name: 'Salvar' })).toHaveClass('button--primary')
  expect(screen.getByRole('button', { name: 'Salvar' })).not.toHaveClass('button--sm')
})

// Padronização: ações de formulário (Cancelar, Salvar, Confirmar...) sempre usam <Button>,
// nunca um <button> estilizado à mão. Tabs, toggles e ícones continuam livres.
const sources = import.meta.glob<string>(
  ['../../**/*.tsx', '!../../**/*.test.tsx', '!../../shared/ui/**'],
  { query: '?raw', import: 'default', eager: true },
)

test('nenhum <button> cru com rótulo de ação fora de shared/ui', () => {
  const actionLabel = /<button\b[^>]*>\s*(Cancelar|Salvar|Confirmar|Voltar|Descartar|Excluir)\b/
  const offenders = Object.entries(sources)
    .filter(([, source]) => actionLabel.test(source))
    .map(([path]) => path)

  expect(Object.keys(sources).length).toBeGreaterThan(20)
  expect(offenders).toEqual([])
})
