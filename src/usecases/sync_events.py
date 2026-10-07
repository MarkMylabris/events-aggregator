import logging
import typing
from dataclasses import dataclass
from datetime import UTC, date, datetime

from src.clients.events_provider import EventsPage, EventsPaginator, ProviderEvent
from src.domain.entities import Event, Place, SyncState, SyncStatus

logger = logging.getLogger(__name__)

FIRST_SYNC_DATE = date(2000, 1, 1)


class EventsProviderClient(typing.Protocol):
    async def events(
        self, changed_at: date, cursor: str | None = None
    ) -> EventsPage: ...


class EventRepository(typing.Protocol):
    async def upsert(self, event: Event) -> None: ...


class SyncStateRepository(typing.Protocol):
    async def get(self) -> SyncState: ...

    async def save(self, state: SyncState) -> None: ...


@dataclass
class SyncResult:
    status: str
    synced_events: int
    last_changed_at: datetime | None
    error: str | None = None


class SyncEventsUsecase:
    def __init__(
        self,
        client: EventsProviderClient,
        events: EventRepository,
        sync_state: SyncStateRepository,
    ) -> None:
        self.client = client
        self.events = events
        self.sync_state = sync_state

    async def do(self) -> SyncResult:
        state = await self.sync_state.get()
        # The provider filters by date only, so the last day is fetched again;
        # upserts make that harmless.
        changed_at = (
            state.last_changed_at.date() if state.last_changed_at else FIRST_SYNC_DATE
        )
        logger.info("Sync started, changed_at=%s", changed_at)

        synced = 0
        last_changed_at = state.last_changed_at
        try:
            async for provider_event in EventsPaginator(self.client, changed_at):
                await self.events.upsert(to_domain(provider_event))
                synced += 1
                if last_changed_at is None or provider_event.changed_at > (
                    last_changed_at
                ):
                    last_changed_at = provider_event.changed_at
        except Exception as exc:
            logger.exception("Sync failed after %s events", synced)
            state.sync_status = SyncStatus.FAILED
            state.error = str(exc)[:2048]
            await self.sync_state.save(state)
            return SyncResult(
                SyncStatus.FAILED, synced, state.last_changed_at, str(exc)
            )

        state.last_sync_time = datetime.now(UTC)
        state.last_changed_at = last_changed_at
        state.sync_status = SyncStatus.SUCCESS
        state.error = None
        await self.sync_state.save(state)
        logger.info(
            "Sync finished: %s events, last_changed_at=%s", synced, last_changed_at
        )
        return SyncResult(SyncStatus.SUCCESS, synced, last_changed_at)


def to_domain(event: ProviderEvent) -> Event:
    place = event.place
    return Event(
        id=event.id,
        name=event.name,
        place=Place(
            id=place.id,
            name=place.name,
            city=place.city,
            address=place.address,
            seats_pattern=place.seats_pattern,
            changed_at=place.changed_at,
            created_at=place.created_at,
        ),
        event_time=event.event_time,
        registration_deadline=event.registration_deadline,
        status=event.status,
        number_of_visitors=event.number_of_visitors,
        changed_at=event.changed_at,
        created_at=event.created_at,
        status_changed_at=event.status_changed_at,
    )
