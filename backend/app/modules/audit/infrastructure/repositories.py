"""SQLAlchemy implementation of `AuditLogWriter`/`AuditLogReader`."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.domain.entities import ActorScope, AuditEntry
from app.modules.audit.infrastructure.models import AuditLogModel


def _to_domain(model: AuditLogModel) -> AuditEntry:
    return AuditEntry(
        id=model.id,
        occurred_at=model.occurred_at,
        actor_user_id=model.actor_user_id,
        actor_scope=ActorScope(model.actor_scope),
        action=model.action,
        entity_type=model.entity_type,
        entity_id=model.entity_id,
        before_state=model.before_state,
        after_state=model.after_state,
        reason=model.reason,
        ip_address=model.ip_address,
        request_id=model.request_id,
    )


class SqlAlchemyAuditLogWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, entry: AuditEntry) -> None:
        self._session.add(
            AuditLogModel(
                id=entry.id,
                occurred_at=entry.occurred_at,
                actor_user_id=entry.actor_user_id,
                actor_scope=entry.actor_scope.value,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                before_state=entry.before_state,
                after_state=entry.after_state,
                reason=entry.reason,
                ip_address=entry.ip_address,
                request_id=entry.request_id,
            )
        )


class SqlAlchemyAuditLogReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: str,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditEntry], int]:
        conditions = (
            AuditLogModel.entity_type == entity_type,
            AuditLogModel.entity_id == entity_id,
        )
        total = self._session.execute(
            select(func.count()).select_from(AuditLogModel).where(*conditions)
        ).scalar_one()
        models = (
            self._session.execute(
                select(AuditLogModel)
                .where(*conditions)
                .order_by(AuditLogModel.occurred_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return [_to_domain(model) for model in models], total
