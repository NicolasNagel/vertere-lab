import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { useSpeciesQuery } from '../../patients/api/use-species-query'
import { Button } from '../../../shared/ui/button'
import { Checkbox } from '../../../shared/ui/checkbox'
import { TagIcon } from '../../../shared/ui/icons'
import { Dropdown } from '../../../shared/ui/dropdown'
import { TextField } from '../../../shared/ui/text-field'
import { ApiError } from '../../../shared/api/errors'
import { useActiveExamCategoriesQuery } from '../api/use-active-exam-categories-query'
import { useCreateExamCategoryMutation } from '../api/use-create-exam-category-mutation'
import { useExamCategoryQuery } from '../api/use-exam-category-query'
import { PanelComponentsField } from './panel-components-field'
import type { Exam, ExamFormValues, ExamStatus } from '../api/catalog-api'
import '../../attendances/components/attendance-draft-page.css'
import './exam-form.css'

const examSchema = z.object({
  name: z.string().trim().min(1, 'Informe o nome do exame.'),
  categoryId: z.string().trim().min(1, 'Selecione a categoria.'),
  description: z.string().trim(),
  priceBase: z.string().trim().min(1, 'Informe o preço base.'),
  status: z.enum(['ACTIVE', 'INACTIVE']),
})

type ExamFormFields = z.infer<typeof examSchema>

const STATUS_OPTIONS: { value: ExamStatus; label: string }[] = [
  { value: 'ACTIVE', label: 'Ativo' },
  { value: 'INACTIVE', label: 'Inativo' },
]

function toFormFields(exam: Exam | null): ExamFormFields {
  return {
    name: exam?.name ?? '',
    categoryId: exam?.categoryId ?? '',
    description: exam?.description ?? '',
    priceBase: exam?.priceBase ?? '',
    status: exam?.status ?? 'ACTIVE',
  }
}

function toApiValues(
  fields: ExamFormFields,
  speciesIds: string[],
  componentExamIds: string[],
): ExamFormValues {
  return {
    componentExamIds,
    name: fields.name,
    categoryId: fields.categoryId,
    description: fields.description || null,
    priceBase: fields.priceBase,
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
  onSubmitUpdate?: (values: ExamFormValues & { status: ExamStatus; reason: string | null }) => void
  // Quando a página que hospeda o form renderiza seus próprios botões de
  // ação (ex.: no header, como no mockup 19), passe `formId` + `hideActions`
  // para que o submit externo aponte para este form via atributo `form=`
  // nativo do HTML, sem duplicar a lógica de submissão.
  formId?: string
  hideActions?: boolean
  /** Cadastro de pacote/perfil (a edição de um pacote existente já é detectada pelo exame). */
  panel?: boolean
  /** `pricing.manage`: sem ele o preço fica só para leitura (o backend recusa a mudança). */
  canManagePrice?: boolean
}

export function ExamForm({
  exam,
  submitting,
  error,
  onCancel,
  onSubmitCreate,
  onSubmitUpdate,
  formId,
  hideActions = false,
  panel = false,
  canManagePrice = true,
}: ExamFormProps) {
  const isPanel = panel || (exam?.isPanel ?? false)
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<ExamFormFields>({
    resolver: zodResolver(examSchema),
    defaultValues: toFormFields(exam),
  })

  const [speciesIds, setSpeciesIds] = useState<string[]>(exam?.speciesIds ?? [])
  const [componentIds, setComponentIds] = useState<string[]>(exam?.componentExamIds ?? [])
  const [componentsError, setComponentsError] = useState<string | null>(null)
  const [speciesError, setSpeciesError] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState<string | null>(null)
  const [newCategoryName, setNewCategoryName] = useState('')
  const [pendingCategoryId, setPendingCategoryId] = useState<string | null>(null)

  const categoriesQuery = useActiveExamCategoriesQuery()
  const speciesQuery = useSpeciesQuery()
  const createCategoryMutation = useCreateExamCategoryMutation()

  // If the exam being edited has a category that was since deactivated, it
  // won't be in categoriesQuery.data (active-only) — fetch it directly so
  // the <select> still has a matching <option> instead of silently
  // resetting to the empty placeholder (same root cause as the quick-create
  // bug: value assigned with no matching option is a no-op).
  const currentCategoryMissing =
    exam !== null &&
    !categoriesQuery.isLoading &&
    !(categoriesQuery.data ?? []).some((category) => category.id === exam.categoryId)
  const missingCategoryQuery = useExamCategoryQuery(currentCategoryMissing ? exam.categoryId : null)

  const categoryOptions = [
    ...(categoriesQuery.data ?? []),
    ...(missingCategoryQuery.data ? [missingCategoryQuery.data] : []),
  ]

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

  // Same class of issue as above: react-hook-form's `register()` sets the
  // <select>'s DOM value once, on mount. If the exam's category is inactive,
  // missingCategoryQuery hasn't resolved yet at that point, so the initial
  // assignment silently fails. Re-apply it once the option actually exists.
  useEffect(() => {
    if (exam && missingCategoryQuery.data?.id === exam.categoryId) {
      setValue('categoryId', exam.categoryId)
    }
  }, [exam, missingCategoryQuery.data, setValue])

  // Same root cause again, for the plain (active-category) edit case: if
  // categoriesQuery is still loading at mount, its <option>s don't exist yet,
  // so register()'s initial value assignment is a no-op — the select is left
  // unselected even though exam.categoryId is valid. Re-apply once the
  // matching option actually appears in the loaded list.
  useEffect(() => {
    if (exam && categoriesQuery.data?.some((category) => category.id === exam.categoryId)) {
      setValue('categoryId', exam.categoryId)
    }
  }, [exam, categoriesQuery.data, setValue])

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
    if (isPanel && componentIds.length < 2) {
      setComponentsError('Um pacote precisa de ao menos 2 exames.')
      return
    }
    setComponentsError(null)
    const ids = isPanel ? componentIds : []
    if (exam) {
      const priceChanged = canManagePrice && fields.priceBase !== (exam.priceBase ?? '')
      const statusChanged = fields.status !== exam.status
      if ((priceChanged || statusChanged) && !reason.trim()) {
        setReasonError('Informe o motivo da alteração de preço ou de status.')
        return
      }
      setReasonError(null)
      onSubmitUpdate?.({
        ...toApiValues(fields, speciesIds, ids),
        // Sem pricing.manage o preço nem é enviado: o backend mantém o atual.
        priceBase: canManagePrice ? fields.priceBase : null,
        status: fields.status,
        reason: reason.trim() || null,
      })
      return
    }
    onSubmitCreate?.(toApiValues(fields, speciesIds, ids))
  })

  const errorMessage = describeError(error)
  const disabled = submitting

  return (
    <form className="attendance-draft-page__stack" id={formId} onSubmit={onSubmit} noValidate>
      <section className="attendance-draft-page__section" aria-labelledby="exam-form-general">
        <h2 id="exam-form-general" className="attendance-draft-page__section-title">
          {isPanel ? 'Identificação do pacote' : 'Identificação'}
        </h2>
        <div className="attendance-draft-page__row">
          <TextField
            id="exam-code"
            label="Código"
            disabled
            value={exam?.code ?? 'Gerado automaticamente ao salvar'}
          />
          <TextField
            id="exam-name"
            label={isPanel ? 'Nome do pacote' : 'Nome'}
            disabled={disabled}
            errorMessage={errors.name?.message}
            {...register('name')}
          />
        </div>
        <TextField
          id="exam-description"
          label="Descrição"
          disabled={disabled}
          {...register('description')}
        />
      </section>

      <section className="attendance-draft-page__section" aria-labelledby="exam-form-category">
        <h2 id="exam-form-category" className="attendance-draft-page__section-title">
          Classificação
        </h2>
        <div className="attendance-draft-page__row">
          <Dropdown
            variant="field"
            label="Categoria"
            icon={<TagIcon />}
            placeholder={categoriesQuery.isLoading ? 'Carregando…' : 'Selecione a categoria'}
            options={categoryOptions.map((category) => ({
              value: category.id,
              label: category.status === 'INACTIVE' ? `${category.name} (inativa)` : category.name,
            }))}
            searchable
            disabled={disabled || categoriesQuery.isLoading}
            value={watch('categoryId')}
            errorMessage={errors.categoryId?.message}
            onChange={(value) => setValue('categoryId', value, { shouldValidate: true })}
          />
          <div className="exam-form__new-category">
            <TextField
              id="exam-new-category"
              label="Criar nova categoria"
              disabled={disabled || createCategoryMutation.isPending}
              value={newCategoryName}
              onChange={(event) => setNewCategoryName(event.target.value)}
            />
            <Button
              type="button"
              variant="secondary"
              disabled={!newCategoryName.trim() || disabled || createCategoryMutation.isPending}
              onClick={handleCreateCategory}
            >
              Criar categoria
            </Button>
          </div>
        </div>
      </section>

      {isPanel && (
        <section className="attendance-draft-page__section" aria-labelledby="exam-form-components">
          <h2 id="exam-form-components" className="attendance-draft-page__section-title">
            Exames do pacote
          </h2>
          <PanelComponentsField
            selectedIds={componentIds}
            disabled={disabled}
            errorMessage={componentsError}
            onChange={(ids) => {
              setComponentIds(ids)
              setComponentsError(null)
            }}
          />
        </section>
      )}

      <section className="attendance-draft-page__section" aria-labelledby="exam-form-price">
        <h2 id="exam-form-price" className="attendance-draft-page__section-title">
          Preço
        </h2>
        <div className="attendance-draft-page__row">
          <TextField
            id="exam-price-base"
            label={isPanel ? 'Preço do pacote' : 'Preço base'}
            inputMode="decimal"
            disabled={disabled || !canManagePrice}
            errorMessage={errors.priceBase?.message}
            {...register('priceBase')}
          />
        </div>
        {!canManagePrice && (
          <p className="attendance-draft-page__hint">
            Alterar preço exige a permissão de gerir preços.
          </p>
        )}
      </section>

      <section className="attendance-draft-page__section" aria-labelledby="exam-form-species">
        <h2 id="exam-form-species" className="attendance-draft-page__section-title">
          Espécies atendidas
        </h2>
        {speciesQuery.isLoading && (
          <p className="attendance-draft-page__hint">Carregando espécies…</p>
        )}
        {!speciesQuery.isLoading && (
          <div className="exam-form__species-list" role="group" aria-label="Espécies">
            {(speciesQuery.data ?? []).map((species) => (
              <Checkbox
                key={species.id}
                label={species.name}
                disabled={disabled}
                checked={speciesIds.includes(species.id)}
                onChange={() => toggleSpecies(species.id)}
              />
            ))}
          </div>
        )}
        {speciesError && (
          <p role="alert" className="attendance-draft-page__domain-error">
            {speciesError}
          </p>
        )}
      </section>

      {exam && (
        <section className="attendance-draft-page__section" aria-labelledby="exam-form-change">
          <h2 id="exam-form-change" className="attendance-draft-page__section-title">
            Situação e motivo da alteração
          </h2>
          <div className="attendance-draft-page__row">
            <Dropdown
              variant="field"
              label="Status"
              options={STATUS_OPTIONS}
              disabled={disabled}
              value={watch('status')}
              onChange={(value) => setValue('status', value as ExamStatus)}
            />
            <TextField
              id="exam-reason"
              label="Motivo (obrigatório ao mudar preço ou status)"
              disabled={disabled}
              value={reason}
              errorMessage={reasonError ?? undefined}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
        </section>
      )}

      {errorMessage && (
        <p role="alert" className="attendance-draft-page__domain-error">
          {errorMessage}
        </p>
      )}

      {!hideActions && (
        <div className="exam-form__actions">
          <Button type="button" variant="cancel" onClick={onCancel} disabled={disabled}>
            Cancelar
          </Button>
          <Button type="submit" disabled={disabled}>
            {disabled ? 'Salvando…' : 'Salvar'}
          </Button>
        </div>
      )}
    </form>
  )
}
