import logging
import typing
import uuid

from src.clients.events_provider import EventsProviderError, EventsProviderNotFound
from src.domain.entities import Event, EventStatus
from src.domain.exceptions import EventNotFound, EventNotPublished, ProviderUnavailable

logger = logging.getLogger(__name__)


class EventsProviderClient(typing.Protocol):
    async def seats(self, event_id: uuid.UUID) -> list[str]: ...


class EventRepository(typing.Protocol):
    async def get(self, event_id: uuid.UUID) -> Event | None: ...


class SeatsCache(typing.Protocol):
    def get(self, key: uuid.UUID) -> list[str] | None: ...

    def set(self, key: uuid.UUID, value: list[str]) -> None: ...


class GetSeatsUsecase:
    def __init__(
        self,
        client: EventsProviderClient,
        events: EventRepository,
        cache: SeatsCache,
    ) -> None:
        self.client = client
        self.events = events
        self.cache = cache

    async def do(self, event_id: uuid.UUID) -> list[str]:
        cached = self.cache.get(event_id)
        if cached is not None:
            return cached

        event = await self.events.get(event_id)
        if event is None:
            raise EventNotFound
        # The provider answers 500 with an HTML page for unpublished events,
        # so check the status on our side first.
        if event.status != EventStatus.PUBLISHED:
            raise EventNotPublished

        try:
            seats = await self.client.seats(event_id)
        except EventsProviderNotFound:
            raise EventNotFound from None
        except (EventsProviderError, OSError) as exc:
            logger.warning("Failed to get seats for %s: %s", event_id, exc)
            raise ProviderUnavailable from exc

        self.cache.set(event_id, seats)
        return seats
