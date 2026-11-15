import { useState } from 'react'

import { Checkbox } from '../../../shared/ui/checkbox'
import { SelectField } from '../../../shared/ui/select'
import { TextField } from '../../../shared/ui/text-field'
import { useSpeciesQuery } from '../../patients/api/use-species-query'
import type { Exam, ExamCategory, ExamFormValues, ExamStatus } from '../api/catalog-api'
import { useUpdateExamMutation } from '../api/use-update-exam-mutation'
import { ExamDetailFooter } from './exam-detail-block'
import { PanelComponentsField } from './panel-components-field'

interface FormProps {
  exam: Exam
  canManagePrice: boolean
  onClose: () => void
}

type Changes = Partial<ExamFormValues & { status: ExamStatus }>

/** O PATCH recebe o conjunto completo: o que o bloco não muda segue como está. Sem
 * `pricing.manage` o preço nem é enviado (o backend mantém o atual). */
function useExamCorrection({ exam, canManagePrice, onClose }: FormProps) {
  const [reason, setReason] = useState('')
  const mutation = useUpdateExamMutation()

  function save(changes: Changes) {
    mutation.mutate(
      {
        id: exam.id,
        values: {
          name: exam.name,
          categoryId: exam.categoryId,
          description: exam.description,
          speciesIds: exam.speciesIds,
          componentExamIds: exam.componentExamIds,
          ...changes,
          priceBase: canManagePrice ? (changes.priceBase ?? exam.priceBase) : null,
          status: changes.status ?? exam.status,
          expectedRowVersion: exam.rowVersion,
          reason: reason.trim(),
        },
      },
      { onSuccess: onClose },
    )
  }

  return { reason, setReason, mutation, save }
}

interface FooterProps {
  exam: Exam
  api: ReturnType<typeof useExamCorrection>
  canSave: boolean
  onSave: () => void
  onClose: () => void
}

function Footer({ exam, api, canSave, onSave, onClose }: FooterProps) {
  return (
    <ExamDetailFooter
      examId={exam.id}
      reason={api.reason}
      onReasonChange={api.setReason}
      canSave={canSave}
      isPending={api.mutation.isPending}
      error={api.mutation.error}
      onSave={onSave}
      onCancel={onClose}
    />
  )
}

export function IdentityForm(props: FormProps) {
  const { exam, onClose } = props
  const api = useExamCorrection(props)
  const [name, setName] = useState(exam.name)
  const [description, setDescription] = useState(exam.description ?? '')
  const changed = name.trim() !== exam.name || description.trim() !== (exam.description ?? '')

  return (
    <div className="exam-detail__form">
      <TextField
        id="exam-edit-name"
        label="Nome"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <TextField
        id="exam-edit-description"
        label="Descrição"
        value={description}
        onChange={(event) => setDescription(event.target.value)}
      />
      <Footer
        exam={exam}
        api={api}
        canSave={changed && name.trim().length > 0}
        onClose={onClose}
        onSave={() => api.save({ name: name.trim(), description: description.trim() || null })}
      />
    </div>
  )
}

export function CategorySpeciesForm(props: FormProps & { categories: ExamCategory[] }) {
  const { exam, onClose, categories } = props
  const api = useExamCorrection(props)
  const speciesQuery = useSpeciesQuery()
  const [categoryId, setCategoryId] = useState(exam.categoryId)
  const [speciesIds, setSpeciesIds] = useState(exam.speciesIds)
  const changed =
    categoryId !== exam.categoryId ||
    speciesIds.length !== exam.speciesIds.length ||
    speciesIds.some((id) => !exam.speciesIds.includes(id))

  return (
    <div className="exam-detail__form">
      <SelectField
        id="exam-edit-category"
        label="Categoria"
        value={categoryId}
        options={categories.map((category) => ({ value: category.id, label: category.name }))}
        onChange={(event) => setCategoryId(event.target.value)}
      />
      <div role="group" aria-label="Espécies atendidas" className="exam-detail__chips">
        {(speciesQuery.data ?? []).map((species) => (
          <Checkbox
            key={species.id}
            label={species.name}
            checked={speciesIds.includes(species.id)}
            onChange={() =>
              setSpeciesIds((current) =>
                current.includes(species.id)
                  ? current.filter((id) => id !== species.id)
                  : [...current, species.id],
              )
            }
          />
        ))}
      </div>
      <Footer
        exam={exam}
        api={api}
        canSave={changed && speciesIds.length > 0}
        onClose={onClose}
        onSave={() => api.save({ categoryId, speciesIds })}
      />
    </div>
  )
}

export function CompositionForm(props: FormProps) {
  const { exam, onClose } = props
  const api = useExamCorrection(props)
  const [ids, setIds] = useState(exam.componentExamIds)
  const changed =
    ids.length !== exam.componentExamIds.length ||
    ids.some((id, index) => id !== exam.componentExamIds[index])

  return (
    <div className="exam-detail__form">
      <PanelComponentsField
        selectedIds={ids}
        errorMessage={ids.length < 2 ? 'Um pacote precisa de ao menos 2 exames.' : null}
        onChange={setIds}
      />
      <Footer
        exam={exam}
        api={api}
        canSave={changed && ids.length >= 2}
        onClose={onClose}
        onSave={() => api.save({ componentExamIds: ids })}
      />
    </div>
  )
}

export function PriceForm(props: FormProps) {
  const { exam, onClose } = props
  const api = useExamCorrection(props)
  const [price, setPrice] = useState(exam.priceBase ?? '')
  const normalized = price.trim().replace(',', '.')

  return (
    <div className="exam-detail__form">
      <TextField
        id="exam-edit-price"
        label={exam.isPanel ? 'Preço do pacote' : 'Preço base'}
        inputMode="decimal"
        value={price}
        onChange={(event) => setPrice(event.target.value)}
      />
      <Footer
        exam={exam}
        api={api}
        canSave={Number(normalized) > 0 && normalized !== (exam.priceBase ?? '')}
        onClose={onClose}
        onSave={() => api.save({ priceBase: normalized })}
      />
    </div>
  )
}

export function StatusForm(props: FormProps) {
  const { exam, onClose } = props
  const api = useExamCorrection(props)
  const [status, setStatus] = useState<ExamStatus>(exam.status)

  return (
    <div className="exam-detail__form">
      <SelectField
        id="exam-edit-status"
        label="Status"
        value={status}
        options={[
          { value: 'ACTIVE', label: 'Ativo' },
          { value: 'INACTIVE', label: 'Inativo' },
        ]}
        onChange={(event) => setStatus(event.target.value as ExamStatus)}
      />
      <Footer
        exam={exam}
        api={api}
        canSave={status !== exam.status}
        onClose={onClose}
        onSave={() => api.save({ status })}
      />
    </div>
  )
}
