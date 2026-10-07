import typing
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time

from src.domain.entities import PROVIDER_TZ, Event
from src.domain.exceptions import EventNotFound


class EventRepository(typing.Protocol):
    async def get(self, event_id: uuid.UUID) -> Event | None: ...

    async def list(
        self, date_from: datetime | None, offset: int, limit: int
    ) -> list[Event]: ...

    async def count(self, date_from: datetime | None) -> int: ...


@dataclass
class EventsPage:
    count: int
    results: list[Event]
    has_next: bool
    has_previous: bool


class ListEventsUsecase:
    def __init__(self, events: EventRepository) -> None:
        self.events = events

    async def do(self, date_from: date | None, page: int, page_size: int) -> EventsPage:
        since = (
            datetime.combine(date_from, time.min, PROVIDER_TZ) if date_from else None
        )
        offset = (page - 1) * page_size
        count = await self.events.count(since)
        results = await self.events.list(since, offset, page_size)
        return EventsPage(
            count=count,
            results=results,
            has_next=offset + page_size < count,
            has_previous=page > 1,
        )


class GetEventUsecase:
    def __init__(self, events: EventRepository) -> None:
        self.events = events

    async def do(self, event_id: uuid.UUID) -> Event:
        event = await self.events.get(event_id)
        if event is None:
            raise EventNotFound
        return event
