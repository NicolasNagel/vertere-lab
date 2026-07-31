"""Per-batch advisory lock — serializes concurrent processing of the same
import batch without imposing a business-wide uniqueness rule on names.

Found via QA against a running instance: two concurrent calls to the same
`/imports/{batch_id}/clinics` (a double-click, or a client retrying a timed
-out request) each read "clinic X not found yet" before either committed,
then both inserted it — `clinics.name`/`veterinarians.name` have no unique
constraint (rightly so: two real clinics or two real veterinarians could
legitimately share a name; that's a product decision, not something an
import-concurrency bug gets to impose globally). The actual invariant that
needs protecting is narrower: *this batch* should only ever be processed by
one request at a time. `pg_advisory_xact_lock` is scoped to the current
transaction (released automatically on commit/rollback — no manual unlock,
no risk of a leaked lock outstaying the request), which is why this needs a
real `Session`/connection and cannot live in a repository-agnostic use case
(`.claude/rules/03-database.md` — "sequência de protocolo... usa lock do
PostgreSQL", same category of problem).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

# Arbitrary but stable namespace for this lock's first key, so it never
# collides with an unrelated advisory lock elsewhere in the system that
# also happens to hash a UUID into the same 32-bit space.
_LOCK_NAMESPACE = 194802


def acquire_batch_lock(session: Session, batch_id: UUID) -> None:
    session.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:batch_id))"),
        {"namespace": _LOCK_NAMESPACE, "batch_id": str(batch_id)},
    )
