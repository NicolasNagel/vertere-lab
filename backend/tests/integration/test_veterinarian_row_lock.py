"""Integração com PostgreSQL real: as mutações de veterinário seguram o lock da linha.

Sem o lock, a checagem "todos os vínculos são da minha clínica" podia ficar velha: o laboratório
vinculava outra clínica entre a checagem e a escrita e a clínica A alterava um registro já
compartilhado. `get_by_id_for_update` serializa as duas operações.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.modules.veterinarians.infrastructure.repositories import SqlAlchemyVeterinarianRepository

pytestmark = pytest.mark.integration


def test_for_update_blocks_a_second_transaction_until_the_first_ends(
    session_factory: sessionmaker[Session],
) -> None:
    vet_id = uuid4()
    with session_factory.begin() as session:
        session.execute(
            text(
                "INSERT INTO veterinarians (id, name, crmv, is_autonomous, status, row_version, "
                "created_at, updated_at) VALUES (:id, 'Vet Lock', 'CRMV-SC 73001', true, 'ACTIVE', 1, "
                "now(), now())"
            ),
            {"id": vet_id},
        )

    holder = session_factory()
    waiter = session_factory()
    try:
        assert SqlAlchemyVeterinarianRepository(holder).get_by_id_for_update(vet_id) is not None
        waiter.execute(text("SET LOCAL lock_timeout = '300ms'"))
        with pytest.raises(OperationalError):
            SqlAlchemyVeterinarianRepository(waiter).get_by_id_for_update(vet_id)
        waiter.rollback()

        holder.rollback()  # releases the lock
        assert SqlAlchemyVeterinarianRepository(waiter).get_by_id_for_update(vet_id) is not None
    finally:
        holder.close()
        waiter.close()
        with session_factory.begin() as session:
            session.execute(text("DELETE FROM veterinarians WHERE id = :id"), {"id": vet_id})
