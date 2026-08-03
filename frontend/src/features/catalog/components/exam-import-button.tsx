import { useRef, type ChangeEvent } from 'react'

import { Button } from '../../../shared/ui/button'
import { UploadIcon } from '../../../shared/ui/icons'
import { ApiError } from '../../../shared/api/errors'
import { useImportExamsMutation } from '../api/use-import-exams-mutation'
import './exam-import-button.css'

function describeError(error: unknown): string | null {
  if (error === null || error === undefined) return null
  if (error instanceof ApiError) return error.message
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}

export function ExamImportButton() {
  const inputRef = useRef<HTMLInputElement>(null)
  const importMutation = useImportExamsMutation()

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    importMutation.mutate(file)
  }

  const errorMessage = describeError(importMutation.error)
  const result = importMutation.data

  return (
    <div className="exam-import-button">
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        className="exam-import-button__input"
        aria-label="Selecionar arquivo CSV para importar exames"
        onChange={handleFileChange}
        disabled={importMutation.isPending}
      />
      <Button
        type="button"
        variant="secondary"
        onClick={() => inputRef.current?.click()}
        disabled={importMutation.isPending}
      >
        <UploadIcon /> {importMutation.isPending ? 'Importando…' : 'Importar CSV'}
      </Button>

      {(result || errorMessage) && (
        <div className="exam-import-button__report" role="status">
          {errorMessage && <p className="exam-import-button__error">{errorMessage}</p>}
          {result && (
            <>
              <p className="exam-import-button__summary">
                {result.importedCount} exame(s) importado(s) com sucesso.
              </p>
              {result.errors.length > 0 && (
                <ul className="exam-import-button__errors">
                  {result.errors.map((error) => (
                    <li key={error.line}>
                      Linha {error.line}: {error.message}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          <button
            type="button"
            className="exam-import-button__dismiss"
            onClick={() => importMutation.reset()}
          >
            Fechar
          </button>
        </div>
      )}
    </div>
  )
}
