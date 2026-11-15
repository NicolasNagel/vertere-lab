import { useQueries } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { ApiError } from "../../../shared/api/errors";
import { formatCurrencyBRL, formatDate } from "../../../shared/lib/formatters";
import { Badge } from "../../../shared/ui/badge";
import { ArrowLeftIcon } from "../../../shared/ui/icons";
import { PageHeader } from "../../../shared/ui/page-header";
import { useAuth } from "../../auth/auth-context";
import { useSpeciesQuery } from "../../patients/api/use-species-query";
import { fetchExam } from "../api/catalog-api";
import { useActiveExamCategoriesQuery } from "../api/use-active-exam-categories-query";
import { examQueryKey, useExamQuery } from "../api/use-exam-query";
import { ExamDetailBlock } from "./exam-detail-block";
import {
  CategorySpeciesForm,
  CompositionForm,
  IdentityForm,
  PriceForm,
  StatusForm,
} from "./exam-detail-forms";
import { ExamSummaryCards } from "./exam-summary-cards";
import "../../../shared/ui/button.css";
import "../../attendances/components/attendance-detail-page.css";
import "../../attendances/components/attendance-readonly-detail.css";

/** Detalhe do exame em blocos, cada um com "Editar" + motivo. Preço só com `pricing.read`
 * e só editável com `pricing.manage`; o backend é quem decide de verdade. */
export function ExamDetailPage() {
  const { examId } = useParams<{ examId: string }>();
  const { user } = useAuth();
  const permissions = user?.permissions ?? [];
  const canEdit = permissions.includes("catalog.manage");
  const canManagePrice = permissions.includes("pricing.manage");

  const examQuery = useExamQuery(examId ?? null);
  const categoriesQuery = useActiveExamCategoriesQuery();
  const speciesQuery = useSpeciesQuery();
  const exam = examQuery.data;
  const componentQueries = useQueries({
    queries: (exam?.componentExamIds ?? []).map((id) => ({
      queryKey: examQueryKey(id),
      queryFn: () => fetchExam(id),
    })),
  });

  const back = (
    <Link to="/cadastros/exames" className="button button--secondary">
      <ArrowLeftIcon />
      Voltar
    </Link>
  );

  if (examQuery.isLoading || examQuery.isError || !exam) {
    const forbidden =
      examQuery.error instanceof ApiError && examQuery.error.status === 403;
    return (
      <div className="attendance-detail-page">
        <PageHeader title="Exame" actions={back} />
        <div className="attendance-detail-page__body">
          {examQuery.isLoading ? (
            <p className="attendance-detail-page__hint">Carregando…</p>
          ) : (
            <p role="alert" className="attendance-detail-page__error">
              {forbidden
                ? "Você não tem permissão para visualizar este exame."
                : "Não foi possível carregar o exame. Tente novamente."}
            </p>
          )}
        </div>
      </div>
    );
  }

  const categories = categoriesQuery.data ?? [];
  const categoryName =
    categories.find((c) => c.id === exam.categoryId)?.name ?? "—";
  const speciesNames = (speciesQuery.data ?? [])
    .filter((s) => exam.speciesIds.includes(s.id))
    .map((s) => s.name)
    .join(" · ");
  const formProps = { exam, canManagePrice, onClose: () => undefined };
  const priceVisible = exam.priceBase !== null;

  return (
    <div className="attendance-detail-page">
      <PageHeader
        title={exam.name}
        subtitle={
          <span className="attendance-detail-page__sub">
            <span className="attendance-readonly-detail__mono">
              {exam.code}
            </span>
            <Badge tone={exam.status === "ACTIVE" ? "success" : "neutral"}>
              {exam.status === "ACTIVE" ? "Ativo" : "Inativo"}
            </Badge>
          </span>
        }
        actions={back}
      />

      <div className="attendance-detail-page__body">
        <ExamSummaryCards
          exam={exam}
          speciesNames={(speciesQuery.data ?? [])
            .filter((s) => exam.speciesIds.includes(s.id))
            .map((s) => s.name)}
        />
        <div className="attendance-readonly-detail">
          <div
            className="attendance-readonly-detail__columns"
            data-money={priceVisible}
          >
            <div className="attendance-readonly-detail__column">
              <ExamDetailBlock
                title="Identificação"
                examId={exam.id}
                canEdit={canEdit}
                form={({ close }) => (
                  <IdentityForm {...formProps} onClose={close} />
                )}
              >
                <dl className="attendance-readonly-detail__fields">
                  <dt>Nome</dt>
                  <dd>{exam.name}</dd>
                  <dt>Código</dt>
                  <dd>{exam.code}</dd>
                  <dt>Descrição</dt>
                  <dd>{exam.description || "—"}</dd>
                </dl>
              </ExamDetailBlock>

              <ExamDetailBlock
                title="Categoria e espécies"
                examId={exam.id}
                canEdit={canEdit}
                form={({ close }) => (
                  <CategorySpeciesForm
                    {...formProps}
                    categories={categories}
                    onClose={close}
                  />
                )}
              >
                <dl className="attendance-readonly-detail__fields">
                  <dt>Categoria</dt>
                  <dd>{categoryName}</dd>
                  <dt>Espécies</dt>
                  <dd>{speciesNames || "—"}</dd>
                </dl>
              </ExamDetailBlock>

              {exam.isPanel && (
                <ExamDetailBlock
                  title="Composição"
                  examId={exam.id}
                  canEdit={canEdit}
                  form={({ close }) => (
                    <CompositionForm {...formProps} onClose={close} />
                  )}
                >
                  <ul className="attendance-readonly-detail__items">
                    {componentQueries.map((query, index) => (
                      <li
                        key={exam.componentExamIds[index]}
                        className="attendance-readonly-detail__item"
                      >
                        {query.data?.name ?? "…"}
                      </li>
                    ))}
                  </ul>
                </ExamDetailBlock>
              )}
            </div>
            <div className="attendance-readonly-detail__column">
              {priceVisible && (
                <ExamDetailBlock
                  title="Preço e vigência"
                  examId={exam.id}
                  canEdit={canEdit && canManagePrice}
                  form={({ close }) => (
                    <PriceForm {...formProps} onClose={close} />
                  )}
                >
                  <dl className="attendance-readonly-detail__fields">
                    <dt>Preço</dt>
                    <dd>{formatCurrencyBRL(exam.priceBase ?? "0")}</dd>
                    <dt>Vigência</dt>
                    <dd>
                      {exam.priceValidFrom && !exam.priceValidFrom.startsWith("1900")
                        ? `desde ${formatDate(exam.priceValidFrom)}`
                        : "Sem data de início"}
                      {exam.priceValidTo
                        ? ` até ${formatDate(exam.priceValidTo)}`
                        : ""}
                    </dd>
                  </dl>
                  {!canManagePrice && (
                    <p className="attendance-readonly-detail__hint">
                      Alterar preço exige a permissão de gerir preços.
                    </p>
                  )}
                </ExamDetailBlock>
              )}

              <ExamDetailBlock
                title="Status"
                examId={exam.id}
                canEdit={canEdit}
                form={({ close }) => (
                  <StatusForm {...formProps} onClose={close} />
                )}
              >
                <dl className="attendance-readonly-detail__fields">
                  <dt>Status</dt>
                  <dd>{exam.status === "ACTIVE" ? "Ativo" : "Inativo"}</dd>
                </dl>
              </ExamDetailBlock>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
