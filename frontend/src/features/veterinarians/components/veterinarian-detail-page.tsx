import { Link, useParams } from 'react-router'

import { ApiError } from '../../../shared/api/errors'
import { displayValue } from '../../../shared/lib/formatters'
import { Badge } from '../../../shared/ui/badge'
import { ArrowLeftIcon, ClinicsIcon, TagIcon, UserIcon } from '../../../shared/ui/icons'
import { PageHeader } from '../../../shared/ui/page-header'
import { useAuth } from '../../auth/auth-context'
import { useVeterinarianQuery } from '../api/use-veterinarian-query'
import { LinkedClinicsList } from './linked-clinics-list'
import { VeterinarianDetailBlock } from './veterinarian-detail-block'
import { ClinicsForm, ContactForm, IdentityForm, StatusForm } from './veterinarian-detail-forms'
import '../../../shared/ui/button.css'
import '../../attendances/components/attendance-detail-page.css'
import '../../../shared/ui/readonly-detail.css'
import '../../attendances/components/attendance-summary-cards.css'
import './veterinarian-detail-page.css'

/** Dois nomes e a contagem do resto: o cartão não pode virar uma lista de 100 clínicas. */
function summarizeClinics(names: string[]): string {
  const shown = names.slice(0, 2).join(' · ')
  return names.length > 2 ? `${shown} e mais ${names.length - 2}` : shown
}

/** Detalhe do veterinário em blocos, cada um com "Editar" + motivo (auditado no backend). */
export function VeterinarianDetailPage() {
  const { veterinarianId } = useParams<{ veterinarianId: string }>()
  const { user } = useAuth()
  const canEdit = user?.permissions.includes('veterinarians.manage') ?? false
  const query = useVeterinarianQuery(veterinarianId ?? null)
  const veterinarian = query.data

  const back = (
    <Link to="/cadastros/veterinarios" className="button button--secondary">
      <ArrowLeftIcon />
      Voltar
    </Link>
  )

  if (query.isLoading || query.isError || !veterinarian) {
    const forbidden = query.error instanceof ApiError && query.error.status === 403
    return (
      <div className="attendance-detail-page">
        <PageHeader title="Veterinário" actions={back} />
        <div className="attendance-detail-page__body">
          {query.isLoading ? (
            <p className="attendance-detail-page__hint">Carregando…</p>
          ) : (
            <p role="alert" className="attendance-detail-page__error">
              {forbidden
                ? 'Você não tem permissão para visualizar este veterinário.'
                : 'Não foi possível carregar o veterinário. Tente novamente.'}
            </p>
          )}
        </div>
      </div>
    )
  }

  const active = veterinarian.status === 'ACTIVE'
  const formProps = { veterinarian, onClose: () => undefined }

  return (
    <div className="attendance-detail-page">
      <PageHeader
        title={veterinarian.name}
        subtitle={
          <span className="attendance-detail-page__sub">
            <span className="attendance-readonly-detail__mono">{veterinarian.crmv}</span>
            <Badge tone={active ? 'success' : 'neutral'}>{active ? 'Ativo' : 'Inativo'}</Badge>
          </span>
        }
        actions={back}
      />

      <div className="attendance-detail-page__body">
        <section
          className="attendance-summary-cards veterinarian-detail-page__cards"
          aria-label="Resumo do veterinário"
        >
          <article className="attendance-summary-card">
            <header className="attendance-summary-card__label">
              <span>Status</span>
              <span className="attendance-summary-card__icon">
                <UserIcon />
              </span>
            </header>
            <strong className="attendance-summary-card__value">
              {active ? 'Ativo' : 'Inativo'}
            </strong>
            <small className="attendance-summary-card__hint">
              {active ? 'disponível para atendimentos' : 'fora de novos atendimentos'}
            </small>
          </article>
          <article className="attendance-summary-card">
            <header className="attendance-summary-card__label">
              <span>Vínculo</span>
              <span className="attendance-summary-card__icon">
                <TagIcon />
              </span>
            </header>
            <strong className="attendance-summary-card__value">
              {veterinarian.isAutonomous ? 'Autônomo' : 'Vinculado'}
            </strong>
            <small className="attendance-summary-card__hint">
              {veterinarian.isAutonomous
                ? 'vínculo com clínica é opcional'
                : 'precisa de ao menos uma clínica'}
            </small>
          </article>
          <article className="attendance-summary-card">
            <header className="attendance-summary-card__label">
              <span>Clínicas</span>
              <span className="attendance-summary-card__icon">
                <ClinicsIcon />
              </span>
            </header>
            <strong className="attendance-summary-card__value">
              {veterinarian.clinics.length}
            </strong>
            <small className="attendance-summary-card__hint">
              {veterinarian.clinics.length > 0
                ? summarizeClinics(veterinarian.clinics.map((clinic) => clinic.clinicName))
                : 'nenhuma clínica vinculada'}
            </small>
          </article>
        </section>

        <div className="attendance-readonly-detail">
          <div className="attendance-readonly-detail__columns" data-money={false}>
            <div className="attendance-readonly-detail__column">
              <VeterinarianDetailBlock
                title="Identificação"
                veterinarianId={veterinarian.id}
                canEdit={canEdit}
                form={({ close }) => <IdentityForm {...formProps} onClose={close} />}
              >
                <dl className="attendance-readonly-detail__fields">
                  <dt>Nome</dt>
                  <dd>{veterinarian.name}</dd>
                  <dt>CRMV</dt>
                  <dd>{veterinarian.crmv}</dd>
                  <dt>Observação</dt>
                  <dd>{displayValue(veterinarian.notes)}</dd>
                </dl>
              </VeterinarianDetailBlock>

              <VeterinarianDetailBlock
                title="Contato"
                veterinarianId={veterinarian.id}
                canEdit={canEdit}
                form={({ close }) => <ContactForm {...formProps} onClose={close} />}
              >
                <dl className="attendance-readonly-detail__fields">
                  <dt>Telefone</dt>
                  <dd>{displayValue(veterinarian.phone)}</dd>
                  <dt>E-mail</dt>
                  <dd>{displayValue(veterinarian.email)}</dd>
                </dl>
              </VeterinarianDetailBlock>
            </div>

            <div className="attendance-readonly-detail__column">
              <VeterinarianDetailBlock
                title="Clínicas vinculadas"
                veterinarianId={veterinarian.id}
                canEdit={canEdit}
                form={({ close }) => <ClinicsForm {...formProps} onClose={close} />}
              >
                {veterinarian.clinics.length === 0 ? (
                  <p className="attendance-readonly-detail__hint">
                    {veterinarian.isAutonomous
                      ? 'Autônomo: o vínculo com clínica é opcional.'
                      : 'Nenhuma clínica vinculada ainda.'}
                  </p>
                ) : (
                  <LinkedClinicsList
                    veterinarianId={veterinarian.id}
                    clinics={veterinarian.clinics}
                  />
                )}
              </VeterinarianDetailBlock>

              <VeterinarianDetailBlock
                title="Status e vínculo"
                veterinarianId={veterinarian.id}
                canEdit={canEdit}
                form={({ close }) => <StatusForm {...formProps} onClose={close} />}
              >
                <dl className="attendance-readonly-detail__fields">
                  <dt>Status</dt>
                  <dd>{active ? 'Ativo' : 'Inativo'}</dd>
                  <dt>Vínculo</dt>
                  <dd>{veterinarian.isAutonomous ? 'Autônomo' : 'Vinculado a clínica'}</dd>
                </dl>
              </VeterinarianDetailBlock>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
