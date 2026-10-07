from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import EventORM, PlaceORM
from src.domain.entities import Event


class SqlEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
