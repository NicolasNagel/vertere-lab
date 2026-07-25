import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { Button } from '../../../shared/ui/button'
import { Checkbox } from '../../../shared/ui/checkbox'
import { SelectField } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import { ApiError } from '../../../shared/api/errors'
import { useActiveExamCategoriesQuery } from '../api/use-active-exam-categories-query'
import { useCreateExamCategoryMutation } from '../api/use-create-exam-category-mutation'
import type { Exam, ExamFormValues, ExamStatus } from '../api/catalog-api'
import './exam-form.css'

type PlantaoMode = 'none' | 'percent' | 'fixed'

const examSchema = z.object({
  code: z.string().trim().min(1, 'Informe o código do exame.'),
  name: z.string().trim().min(1, 'Informe o nome do exame.'),
  categoryId: z.string().trim().min(1, 'Selecione a categoria.'),
  description: z.string().trim(),
  priceBase: z.string().trim().min(1, 'Informe o preço base.'),
  plantaoMode: z.enum(['none', 'percent', 'fixed']),
  plantaoValue: z.string().trim(),
  status: z.enum(['ACTIVE', 'INACTIVE']),
})

type ExamFormFields = z.infer<typeof examSchema>

const STATUS_OPTIONS: { value: ExamStatus; label: string }[] = [
  { value: 'ACTIVE', label: 'Ativo' },
  { value: 'INACTIVE', label: 'Inativo' },
]

function plantaoModeOf(exam: Exam | null): PlantaoMode {
  if (!exam) return 'none'
  if (exam.plantaoSurchargePercent) return 'percent'
  if (exam.plantaoSurchargeFixed) return 'fixed'
  return 'none'
}

function toFormFields(exam: Exam | null): ExamFormFields {
  return {
    code: exam?.code ?? '',
    name: exam?.name ?? '',
    categoryId: exam?.categoryId ?? '',
    description: exam?.description ?? '',
    priceBase: exam?.priceBase ?? '',
    plantaoMode: plantaoModeOf(exam),
    plantaoValue: exam?.plantaoSurchargePercent ?? exam?.plantaoSurchargeFixed ?? '',
    status: exam?.status ?? 'ACTIVE',
  }
}

function toApiValues(fields: ExamFormFields, speciesIds: string[]): ExamFormValues {
  return {
    code: fields.code,
    name: fields.name,
    categoryId: fields.categoryId,
    description: fields.description || null,
    priceBase: fields.priceBase,
    plantaoSurchargePercent: fields.plantaoMode === 'percent' ? fields.plantaoValue : null,
    plantaoSurchargeFixed: fields.plantaoMode === 'fixed' ? fields.plantaoValue : null,
    speciesIds,
  }
}

function describeError(error: unknown): string | null {
  if (error === null || error === undefined) {
    return null
  }
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Falha de conexão. Verifique sua internet e tente novamente.'
}

interface ExamFormProps {
  exam: Exam | null
  submitting: boolean
  error?: unknown
  onCancel: () => void
  onSubmitCreate?: (values: ExamFormValues) => void
  onSubmitUpdate?: (values: ExamFormValues & { status: ExamStatus }) => void
}

export function ExamForm({
  exam,
  submitting,
  error,
  onCancel,
  onSubmitCreate,
  onSubmitUpdate,
}: ExamFormProps) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<ExamFormFields>({
    resolver: zodResolver(examSchema),
    defaultValues: toFormFields(exam),
  })

  const plantaoMode = watch('plantaoMode')
  const [speciesIds, setSpeciesIds] = useState<string[]>(exam?.speciesIds ?? [])
  const [speciesError, setSpeciesError] = useState<string | null>(null)
  const [newCategoryName, setNewCategoryName] = useState('')
  const [pendingCategoryId, setPendingCategoryId] = useState<string | null>(null)

  const categoriesQuery = useActiveExamCategoriesQuery()
  const speciesQuery = useSpeciesQuery()
  const createCategoryMutation = useCreateExamCategoryMutation()

  // The category list refetches asynchronously after creation — setting the
  // select's value before its <option> exists in the DOM is a no-op (native
  // <select> silently ignores an unmatched value). Wait for the option to
  // actually appear in the refetched list before selecting it.
  useEffect(() => {
    if (!pendingCategoryId) return
    if (categoriesQuery.data?.some((category) => category.id === pendingCategoryId)) {
      setValue('categoryId', pendingCategoryId)
      setPendingCategoryId(null)
    }
  }, [pendingCategoryId, categoriesQuery.data, setValue])

  function toggleSpecies(speciesId: string) {
    setSpeciesIds((current) =>
      current.includes(speciesId)
        ? current.filter((id) => id !== speciesId)
        : [...current, speciesId],
    )
  }

  function handleCreateCategory() {
    if (!newCategoryName.trim()) return
    createCategoryMutation.mutate(newCategoryName.trim(), {
      onSuccess: (category) => {
        setPendingCategoryId(category.id)
        setNewCategoryName('')
      },
    })
  }

  const onSubmit = handleSubmit((fields) => {
    if (speciesIds.length === 0) {
      setSpeciesError('Selecione ao menos uma espécie atendida.')
      return
    }
    setSpeciesError(null)
    if (exam) {
      onSubmitUpdate?.({ ...toApiValues(fields, speciesIds), status: fields.status })
      return
    }
    onSubmitCreate?.(toApiValues(fields, speciesIds))
  })

  const errorMessage = describeError(error)

  return (
    <form className="exam-form" onSubmit={onSubmit} noValidate>
      <div className="exam-form__row">
        <TextField
          id="exam-code"
          label="Código"
          disabled={submitting}
          errorMessage={errors.code?.message}
          {...register('code')}
        />
        {exam && (
          <SelectField
            id="exam-status"
            label="Status"
            options={STATUS_OPTIONS}
            disabled={submitting}
            {...register('status')}
          />
        )}
      </div>

      <TextField
        id="exam-name"
        label="Nome"
        disabled={submitting}
        errorMessage={errors.name?.message}
        {...register('name')}
      />

      <TextField
        id="exam-description"
        label="Descrição"
        disabled={submitting}
        {...register('description')}
      />

      <div className="exam-form__row">
        <SelectField
          id="exam-category"
          label="Categoria"
          options={[
            { value: '', label: categoriesQuery.isLoading ? 'Carregando…' : 'Selecione…' },
            ...(categoriesQuery.data ?? []).map((category) => ({
              value: category.id,
              label: category.name,
            })),
          ]}
          disabled={submitting || categoriesQuery.isLoading}
          errorMessage={errors.categoryId?.message}
          {...register('categoryId')}
        />
      </div>
      <div className="exam-form__new-category">
        <TextField
          id="exam-new-category"
          label="Criar nova categoria"
          disabled={submitting || createCategoryMutation.isPending}
          value={newCategoryName}
          onChange={(event) => setNewCategoryName(event.target.value)}
        />
        <Button
          type="button"
          variant="ghost"
          disabled={!newCategoryName.trim() || submitting || createCategoryMutation.isPending}
          onClick={handleCreateCategory}
        >
          Criar categoria
        </Button>
      </div>

      <TextField
        id="exam-price-base"
        label="Preço base"
        disabled={submitting}
        errorMessage={errors.priceBase?.message}
        {...register('priceBase')}
      />

      <div className="exam-form__row">
        <SelectField
          id="exam-plantao-mode"
          label="Adicional de plantão"
          options={[
            { value: 'none', label: 'Sem adicional' },
            { value: 'percent', label: 'Percentual' },
            { value: 'fixed', label: 'Valor fixo' },
          ]}
          disabled={submitting}
          {...register('plantaoMode')}
        />
        {plantaoMode !== 'none' && (
          <TextField
            id="exam-plantao-value"
            label={plantaoMode === 'percent' ? 'Percentual (%)' : 'Valor fixo'}
            disabled={submitting}
            {...register('plantaoValue')}
          />
        )}
      </div>

      <p className="exam-form__section-title">Espécies atendidas</p>
      {speciesQuery.isLoading && <p className="exam-form__hint">Carregando espécies…</p>}
      {!speciesQuery.isLoading && (
        <div className="exam-form__species-list" role="group" aria-label="Espécies">
          {(speciesQuery.data ?? []).map((species) => (
            <Checkbox
              key={species.id}
              label={species.name}
              disabled={submitting}
              checked={speciesIds.includes(species.id)}
              onChange={() => toggleSpecies(species.id)}
            />
          ))}
        </div>
      )}
      {speciesError && (
        <p role="alert" className="exam-form__domain-error">
          {speciesError}
        </p>
      )}

      {errorMessage && (
        <p role="alert" className="exam-form__domain-error">
          {errorMessage}
        </p>
      )}

      <div className="exam-form__actions">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
        <Button type="submit" className="exam-form__submit" disabled={submitting}>
          {submitting ? 'Salvando…' : 'Salvar'}
        </Button>
      </div>
    </form>
  )
}
