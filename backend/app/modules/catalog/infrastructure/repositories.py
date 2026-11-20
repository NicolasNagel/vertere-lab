"""SQLAlchemy implementation of the catalog repository protocols.

Domain entities are the only thing that crosses back out of this module;
ORM models never leak past this file (rule: .claude/rules/03-database.md).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session as SqlAlchemySession

from app.modules.catalog.domain.entities import Exam, ExamCategory, ExamCategoryStatus, ExamStatus
from app.modules.catalog.domain.value_objects import ExamCode
from app.modules.catalog.infrastructure.models import (
    ExamCategoryModel,
    ExamModel,
    ExamPanelItemModel,
    ExamSpeciesModel,
)
from app.shared.infrastructure.sql import LIKE_ESCAPE, folded, folded_pattern


def _category_to_domain(model: ExamCategoryModel) -> ExamCategory:
    return ExamCategory(
        id=model.id,
        name=model.name,
        status=ExamCategoryStatus(model.status),
        created_by=model.created_by,
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        row_version=model.row_version,
    )


class SqlAlchemyExamCategoryRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def get_by_id(self, category_id: UUID) -> ExamCategory | None:
        model = self._session.get(ExamCategoryModel, category_id)
        return _category_to_domain(model) if model is not None else None

    def get_by_name(self, name: str) -> ExamCategory | None:
        model = self._session.execute(
            select(ExamCategoryModel).where(func.lower(ExamCategoryModel.name) == name.lower())
        ).scalar_one_or_none()
        return _category_to_domain(model) if model is not None else None

    def add(self, category: ExamCategory) -> None:
        self._session.add(
            ExamCategoryModel(
                id=category.id,
                name=category.name,
                status=category.status.value,
                created_by=category.created_by,
                updated_by=category.updated_by,
                created_at=category.created_at,
                updated_at=category.updated_at,
                row_version=category.row_version,
            )
        )

    def save(self, category: ExamCategory) -> None:
        model = self._session.get(ExamCategoryModel, category.id)
        if model is None:
            raise LookupError(f"Categoria {category.id} não encontrada para atualização.")
        model.name = category.name
        model.status = category.status.value
        model.updated_by = category.updated_by
        model.updated_at = category.updated_at
        model.row_version = category.row_version + 1
        category.row_version = model.row_version

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ExamCategoryStatus | None,
        search: str | None,
    ) -> tuple[list[ExamCategory], int]:
        conditions: list[ColumnElement[bool]] = []
        if status is not None:
            conditions.append(ExamCategoryModel.status == status.value)
        if search:
            like_pattern = folded_pattern(search)
            conditions.append(folded(ExamCategoryModel.name).like(like_pattern, escape=LIKE_ESCAPE))

        count_stmt = select(func.count()).select_from(ExamCategoryModel)
        list_stmt = select(ExamCategoryModel).order_by(ExamCategoryModel.name)
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = self._session.execute(count_stmt).scalar_one()
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(list_stmt).scalars().all()
        return [_category_to_domain(model) for model in models], total

    def list_all_active(self) -> list[ExamCategory]:
        models = (
            self._session.execute(
                select(ExamCategoryModel)
                .where(ExamCategoryModel.status == ExamCategoryStatus.ACTIVE.value)
                .order_by(ExamCategoryModel.name)
            )
            .scalars()
            .all()
        )
        return [_category_to_domain(model) for model in models]


class SqlAlchemyExamRepository:
    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session

    def _species_ids_for(self, exam_id: UUID) -> frozenset[UUID]:
        rows = self._session.execute(
            select(ExamSpeciesModel.species_id).where(ExamSpeciesModel.exam_id == exam_id)
        ).scalars()
        return frozenset(rows)

    def _component_ids_for(self, exam_id: UUID) -> tuple[UUID, ...]:
        rows = self._session.execute(
            select(ExamPanelItemModel.component_id)
            .where(ExamPanelItemModel.panel_id == exam_id)
            .order_by(ExamPanelItemModel.position)
        ).scalars()
        return tuple(rows)

    def _sync_components(self, exam_id: UUID, component_ids: tuple[UUID, ...]) -> None:
        existing = self._session.execute(
            select(ExamPanelItemModel).where(ExamPanelItemModel.panel_id == exam_id)
        ).scalars()
        for link in existing:
            self._session.delete(link)
        self._session.flush()
        for position, component_id in enumerate(component_ids):
            self._session.add(
                ExamPanelItemModel(panel_id=exam_id, component_id=component_id, position=position)
            )

    def get_many_by_ids(self, exam_ids: list[UUID]) -> list[Exam]:
        if not exam_ids:
            return []
        models = self._session.execute(
            select(ExamModel).where(ExamModel.id.in_(exam_ids))
        ).scalars()
        return [self._to_domain(model) for model in models]

    def list_active_panels_containing(self, exam_id: UUID) -> list[Exam]:
        models = self._session.execute(
            select(ExamModel)
            .join(ExamPanelItemModel, ExamPanelItemModel.panel_id == ExamModel.id)
            .where(
                ExamPanelItemModel.component_id == exam_id,
                ExamModel.status == ExamStatus.ACTIVE.value,
            )
            .order_by(ExamModel.name)
        ).scalars()
        return [self._to_domain(model) for model in models]

    def _to_domain(self, model: ExamModel) -> Exam:
        return Exam(
            id=model.id,
            code=ExamCode(model.code),
            name=model.name,
            category_id=model.category_id,
            description=model.description,
            price_base=model.price_base,
            price_valid_from=model.price_valid_from,
            price_valid_to=model.price_valid_to,
            species_ids=self._species_ids_for(model.id),
            component_ids=self._component_ids_for(model.id),
            status=ExamStatus(model.status),
            created_by=model.created_by,
            updated_by=model.updated_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            row_version=model.row_version,
        )

    def _sync_species(self, exam_id: UUID, species_ids: frozenset[UUID]) -> None:
        existing = self._session.execute(
            select(ExamSpeciesModel).where(ExamSpeciesModel.exam_id == exam_id)
        ).scalars()
        for link in existing:
            self._session.delete(link)
        self._session.flush()
        for species_id in species_ids:
            self._session.add(ExamSpeciesModel(exam_id=exam_id, species_id=species_id))

    def get_by_id(self, exam_id: UUID) -> Exam | None:
        model = self._session.get(ExamModel, exam_id)
        return self._to_domain(model) if model is not None else None

    def get_by_code(self, code: str) -> Exam | None:
        model = self._session.execute(
            select(ExamModel).where(ExamModel.code == code)
        ).scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    def list_all_names(self) -> dict[str, UUID]:
        rows = self._session.execute(select(ExamModel.id, ExamModel.name)).all()
        return {name.lower(): id_ for id_, name in rows}

    def add(self, exam: Exam) -> None:
        self._session.add(
            ExamModel(
                id=exam.id,
                code=str(exam.code),
                name=exam.name,
                category_id=exam.category_id,
                description=exam.description,
                price_base=exam.price_base,
                price_valid_from=exam.price_valid_from,
                price_valid_to=exam.price_valid_to,
                status=exam.status.value,
                created_by=exam.created_by,
                updated_by=exam.updated_by,
                created_at=exam.created_at,
                updated_at=exam.updated_at,
                row_version=exam.row_version,
            )
        )
        self._session.flush()
        self._sync_species(exam.id, exam.species_ids)
        self._sync_components(exam.id, exam.component_ids)

    def save(self, exam: Exam) -> None:
        model = self._session.get(ExamModel, exam.id)
        if model is None:
            raise LookupError(f"Exame {exam.id} não encontrado para atualização.")
        model.code = str(exam.code)
        model.name = exam.name
        model.category_id = exam.category_id
        model.description = exam.description
        model.price_base = exam.price_base
        model.price_valid_from = exam.price_valid_from
        model.price_valid_to = exam.price_valid_to
        model.status = exam.status.value
        model.updated_by = exam.updated_by
        model.updated_at = exam.updated_at
        model.row_version = exam.row_version + 1
        exam.row_version = model.row_version
        self._sync_species(exam.id, exam.species_ids)
        self._sync_components(exam.id, exam.component_ids)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        status: ExamStatus | None,
        category_id: UUID | None,
        species_id: UUID | None,
        search: str | None,
    ) -> tuple[list[Exam], int]:
        conditions: list[ColumnElement[bool]] = []
        if status is not None:
            conditions.append(ExamModel.status == status.value)
        if category_id is not None:
            conditions.append(ExamModel.category_id == category_id)
        if search:
            like_pattern = folded_pattern(search)
            conditions.append(
                or_(
                    folded(ExamModel.name).like(like_pattern, escape=LIKE_ESCAPE),
                    folded(ExamModel.code).like(like_pattern, escape=LIKE_ESCAPE),
                )
            )

        count_stmt = select(func.count()).select_from(ExamModel)
        list_stmt = select(ExamModel).order_by(ExamModel.name)
        if species_id is not None:
            species_subquery = select(ExamSpeciesModel.exam_id).where(
                ExamSpeciesModel.species_id == species_id
            )
            count_stmt = count_stmt.where(ExamModel.id.in_(species_subquery))
            list_stmt = list_stmt.where(ExamModel.id.in_(species_subquery))
        for condition in conditions:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = self._session.execute(count_stmt).scalar_one()
        list_stmt = list_stmt.offset((page - 1) * page_size).limit(page_size)
        models = self._session.execute(list_stmt).scalars().all()
        return [self._to_domain(model) for model in models], total
