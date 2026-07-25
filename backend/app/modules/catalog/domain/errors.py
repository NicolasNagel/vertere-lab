"""Catalog-specific domain errors — stable codes, safe messages."""

from __future__ import annotations

from app.shared.domain.errors import ConflictError, ValidationError


class DuplicateExamCategoryNameError(ConflictError):
    pass


class DuplicateExamCodeError(ConflictError):
    pass


class InvalidPlantaoSurchargeError(ValidationError):
    pass
