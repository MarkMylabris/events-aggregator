import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import EventORM, PlaceORM
from src.domain.entities import Event, Place


class SqlEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, event_id: uuid.UUID) -> Event | None:
        row = await self.session.get(EventORM, event_id)
        return to_entity(row) if row else None

    async def list(
        self, date_from: datetime | None, offset: int, limit: int
    ) -> list[Event]:
        query = (
            self._filtered(select(EventORM), date_from)
            .order_by(EventORM.event_time, EventORM.id)
            .offset(offset)
            .limit(limit)
        )
        rows = await self.session.scalars(query)
        return [to_entity(row) for row in rows]

    async def count(self, date_from: datetime | None) -> int:
        query = self._filtered(select(func.count(EventORM.id)), date_from)
        return await self.session.scalar(query) or 0

    async def upsert(self, event: Event) -> None:
        place = event.place
        place_values = {
            "id": place.id,
            "name": place.name,
            "city": place.city,
            "address": place.address,
            "seats_pattern": place.seats_pattern,
            "changed_at": place.changed_at,
            "created_at": place.created_at,
        }
        await self.session.execute(
            insert(PlaceORM)
            .values(place_values)
            .on_conflict_do_update(index_elements=["id"], set_=place_values)
        )

        event_values = {
            "id": event.id,
            "name": event.name,
            "place_id": place.id,
            "event_time": event.event_time,
            "registration_deadline": event.registration_deadline,
            "status": event.status,
            "number_of_visitors": event.number_of_visitors,
            "changed_at": event.changed_at,
            "created_at": event.created_at,
            "status_changed_at": event.status_changed_at,
        }
        await self.session.execute(
            insert(EventORM)
            .values(event_values)
            .on_conflict_do_update(index_elements=["id"], set_=event_values)
        )

    def _filtered(self, query: Select, date_from: datetime | None) -> Select:
        if date_from is not None:
            query = query.where(EventORM.event_time >= date_from)
        return query


def to_entity(row: EventORM) -> Event:
    place = row.place
    return Event(
        id=row.id,
        name=row.name,
        place=Place(
            id=place.id,
            name=place.name,
            city=place.city,
            address=place.address,
            seats_pattern=place.seats_pattern,
            changed_at=place.changed_at,
            created_at=place.created_at,
        ),
        event_time=row.event_time,
        registration_deadline=row.registration_deadline,
        status=row.status,
        number_of_visitors=row.number_of_visitors,
        changed_at=row.changed_at,
        created_at=row.created_at,
        status_changed_at=row.status_changed_at,
    )
