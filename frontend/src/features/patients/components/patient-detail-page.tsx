import { useMemo } from 'react'
import { Link, useParams } from 'react-router'

import { displayValue } from '../../../shared/lib/formatters'
import { useActionError } from '../../../shared/lib/use-action-error'
import { Badge } from '../../../shared/ui/badge'
import { Button } from '../../../shared/ui/button'
import { DetailBlock } from '../../../shared/ui/detail-block'
import { ArrowLeftIcon, ClinicsIcon, PatientsIcon, UserIcon } from '../../../shared/ui/icons'
import { PageHeader } from '../../../shared/ui/page-header'
import { useAuth } from '../../auth/auth-context'
import { useAllClinicsQuery } from '../../clinics/api/use-clinics-query'
import { useDeactivatePatientMutation } from '../api/use-deactivate-patient-mutation'
import { usePatientQuery } from '../api/use-patient-query'
import { useReactivatePatientMutation } from '../api/use-reactivate-patient-mutation'
import { useSpeciesQuery } from '../api/use-species-query'
import { ClinicForm, IdentityForm, NotesForm, OwnerForm } from './patient-detail-forms'
import {
  PATIENT_SEX_LABELS,
  PATIENT_STATUS_LABELS,
  patientLoadErrorMessage,
} from './patient-labels'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-detail-page.css'
import '../../../shared/ui/readonly-detail.css'
import '../../attendances/components/attendance-summary-cards.css'
import './patient-detail-page.css'

/** Detalhe do paciente em blocos, cada um com "Editar" (a troca de clínica exige motivo). */
export function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const { user } = useAuth()
  const canManage = user?.permissions.includes('patients.manage') ?? false
  const query = usePatientQuery(patientId ?? null)
  const speciesQuery = useSpeciesQuery()
  const clinicsQuery = useAllClinicsQuery()
  const deactivateMutation = useDeactivatePatientMutation()
  const reactivateMutation = useReactivatePatientMutation()
  const actionError = useActionError()
  const patient = query.data

  const speciesName = useMemo(
    () => speciesQuery.data?.find((species) => species.id === patient?.speciesId)?.name ?? '—',
    [speciesQuery.data, patient?.speciesId],
  )
  const clinicName = useMemo(() => {
    if (!patient?.clinicId) return 'Sem clínica'
    return clinicsQuery.data?.items.find((clinic) => clinic.id === patient.clinicId)?.name ?? '—'
  }, [clinicsQuery.data, patient?.clinicId])

  const back = (
    <Link to="/pacientes" className="button button--secondary">
      <ArrowLeftIcon />
      Voltar
    </Link>
  )

  if (query.isLoading || query.isError || !patient) {
    return (
      <div className="attendance-detail-page">
        <PageHeader title="Paciente" actions={back} />
        <div className="attendance-detail-page__body">
          {query.isLoading ? (
            <p className="attendance-detail-page__hint">Carregando…</p>
          ) : (
            <p role="alert" className="attendance-detail-page__error">
              {patientLoadErrorMessage(query.error)}
            </p>
          )}
        </div>
      </div>
    )
  }

  const active = patient.status === 'ACTIVE'
  const canEdit = canManage && active

  function toggleStatus() {
    if (!patient) return
    actionError.clear()
    const mutation = active ? deactivateMutation : reactivateMutation
    mutation.mutate(patient.id, { onError: actionError.onError })
  }

  return (
    <div className="attendance-detail-page">
      <PageHeader
        title={patient.name}
        subtitle={
          <span className="attendance-detail-page__sub">
            <span>{speciesName}</span>
            <Badge tone={active ? 'success' : 'neutral'}>{PATIENT_STATUS_LABELS[patient.status]}</Badge>
          </span>
        }
        actions={
          <>
            {canManage && (
              <Button type="button" variant="secondary" onClick={toggleStatus}>
                {active ? 'Inativar paciente' : 'Reativar paciente'}
              </Button>
            )}
            {back}
          </>
        }
      />

      <div className="attendance-detail-page__body">
        {actionError.message && (
          <p role="alert" className="attendance-detail-page__error">
            {actionError.message}
          </p>
        )}
        {!active && (
          <p className="attendance-detail-page__hint">
            Paciente inativo: somente leitura até reativar.
          </p>
        )}

        <section
          className="attendance-summary-cards patient-detail-page__cards"
          aria-label="Resumo do paciente"
        >
          <article className="attendance-summary-card">
            <header className="attendance-summary-card__label">
              <span>Status</span>
              <span className="attendance-summary-card__icon">
                <UserIcon />
              </span>
            </header>
            <strong className="attendance-summary-card__value">
              {PATIENT_STATUS_LABELS[patient.status]}
            </strong>
            <small className="attendance-summary-card__hint">
              {active ? 'disponível para atendimentos' : 'fora de novos atendimentos'}
            </small>
          </article>
          <article className="attendance-summary-card">
            <header className="attendance-summary-card__label">
              <span>Espécie</span>
              <span className="attendance-summary-card__icon">
                <PatientsIcon />
              </span>
            </header>
            <strong className="attendance-summary-card__value">{speciesName}</strong>
            <small className="attendance-summary-card__hint">
              {PATIENT_SEX_LABELS[patient.sex]} · {displayValue(patient.ageDescription)}
            </small>
          </article>
          <article className="attendance-summary-card">
            <header className="attendance-summary-card__label">
              <span>Clínica</span>
              <span className="attendance-summary-card__icon">
                <ClinicsIcon />
              </span>
            </header>
            <strong className="attendance-summary-card__value">{clinicName}</strong>
            <small className="attendance-summary-card__hint">
              tutor: {patient.ownerName}
            </small>
          </article>
        </section>

        <div className="attendance-readonly-detail">
          <div className="attendance-readonly-detail__columns" data-money={false}>
            <div className="attendance-readonly-detail__column">
              <DetailBlock
                title="Identificação"
                canEdit={canEdit}
                form={({ close }) => <IdentityForm patient={patient} onClose={close} />}
              >
                <dl className="attendance-readonly-detail__fields patient-detail-page__fields">
                  <dt>Nome</dt>
                  <dd>{patient.name}</dd>
                  <dt>Espécie</dt>
                  <dd>{speciesName}</dd>
                  <dt>Raça</dt>
                  <dd>{displayValue(patient.breed)}</dd>
                  <dt>Sexo</dt>
                  <dd>{PATIENT_SEX_LABELS[patient.sex]}</dd>
                  <dt>Idade</dt>
                  <dd>{displayValue(patient.ageDescription)}</dd>
                </dl>
              </DetailBlock>

              <DetailBlock
                title="Tutor"
                canEdit={canEdit}
                form={({ close }) => <OwnerForm patient={patient} onClose={close} />}
              >
                <dl className="attendance-readonly-detail__fields patient-detail-page__fields">
                  <dt>Nome</dt>
                  <dd>{patient.ownerName}</dd>
                  <dt>Telefone</dt>
                  <dd>{displayValue(patient.ownerPhone)}</dd>
                  <dt>Documento</dt>
                  <dd>{displayValue(patient.ownerDocument)}</dd>
                </dl>
              </DetailBlock>
            </div>

            <div className="attendance-readonly-detail__column">
              <DetailBlock
                title="Clínica"
                canEdit={canEdit}
                form={({ close }) => <ClinicForm patient={patient} onClose={close} />}
              >
                <dl className="attendance-readonly-detail__fields patient-detail-page__fields">
                  <dt>Clínica</dt>
                  <dd>{clinicName}</dd>
                </dl>
              </DetailBlock>

              <DetailBlock
                title="Observação"
                canEdit={canEdit}
                form={({ close }) => <NotesForm patient={patient} onClose={close} />}
              >
                <p className="attendance-readonly-detail__note patient-detail-page__fields">
                  {displayValue(patient.notes)}
                </p>
              </DetailBlock>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
