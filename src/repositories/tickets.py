import uuid

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import TicketORM
from src.domain.entities import Ticket


class SqlTicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, ticket: Ticket) -> None:
        values = {
            "id": ticket.id,
            "event_id": ticket.event_id,
            "first_name": ticket.first_name,
            "last_name": ticket.last_name,
            "email": ticket.email,
            "seat": ticket.seat,
        }
        # The provider gives the same ticket id to the next person who takes
        # a released seat, so an existing row is overwritten.
        await self.session.execute(
            insert(TicketORM)
            .values(values)
            .on_conflict_do_update(index_elements=["id"], set_=values)
        )
        await self.session.commit()

    async def get(self, ticket_id: uuid.UUID) -> Ticket | None:
        row = await self.session.get(TicketORM, ticket_id)
        if row is None:
            return None
        return Ticket(
            id=row.id,
            event_id=row.event_id,
            first_name=row.first_name,
            last_name=row.last_name,
            email=row.email,
            seat=row.seat,
        )

    async def delete(self, ticket_id: uuid.UUID) -> None:
        await self.session.execute(delete(TicketORM).where(TicketORM.id == ticket_id))
        await self.session.commit()
