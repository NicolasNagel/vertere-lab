import './closure-view-mode-toggle.css'

export type ClosureItemsViewMode = 'exame' | 'protocolo'

interface ClosureViewModeToggleProps {
  mode: ClosureItemsViewMode
  onChange: (mode: ClosureItemsViewMode) => void
}

export function ClosureViewModeToggle({ mode, onChange }: ClosureViewModeToggleProps) {
  return (
    <div className="closure-view-mode-toggle" role="group" aria-label="Agrupar itens por">
      <button
        type="button"
        className="closure-view-mode-toggle__option"
        data-active={mode === 'exame'}
        onClick={() => onChange('exame')}
      >
        Por exame
      </button>
      <button
        type="button"
        className="closure-view-mode-toggle__option"
        data-active={mode === 'protocolo'}
        onClick={() => onChange('protocolo')}
      >
        Por protocolo
      </button>
    </div>
  )
}
