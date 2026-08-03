from __future__ import annotations

from app.modules.catalog.application.dtos import ExamCategoryDTO, ExamDTO
from app.modules.catalog.domain.entities import Exam, ExamCategory


def exam_category_to_dto(category: ExamCategory) -> ExamCategoryDTO:
    return ExamCategoryDTO(
        id=category.id,
        name=category.name,
        status=category.status.value,
        created_at=category.created_at,
        updated_at=category.updated_at,
        row_version=category.row_version,
    )


def exam_to_dto(exam: Exam, *, include_price: bool) -> ExamDTO:
    return ExamDTO(
        id=exam.id,
        code=str(exam.code),
        name=exam.name,
        category_id=exam.category_id,
        description=exam.description,
        species_ids=exam.species_ids,
        status=exam.status.value,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        row_version=exam.row_version,
        price_base=exam.price_base if include_price else None,
        price_valid_from=exam.price_valid_from if include_price else None,
        price_valid_to=exam.price_valid_to if include_price else None,
    )
