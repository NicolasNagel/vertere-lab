"""Veterinarian-clinic link domain errors — stable codes, safe messages."""

from __future__ import annotations

from app.shared.domain.errors import ConflictError


class LastClinicLinkRequiredError(ConflictError):
    """Raised when removing a link would leave a non-autonomous veterinarian
    with zero linked clinics — violates the acceptance criterion in
    assets/features/screens/spec-pages.md ("veterinário não autônomo exige
    ao menos uma [clínica]")."""
