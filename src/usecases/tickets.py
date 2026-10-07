import logging
import typing
import uuid
from datetime import UTC, datetime

from src.clients.events_provider import (
    EventsProviderBadRequest,
    EventsProviderError,
    EventsProviderNotFound,
)
from src.domain.entities import Event, EventStatus, Ticket
from src.domain.exceptions import (
    CancellationRejected,
    EventNotFound,
    EventNotPublished,
    InvalidSeat,
    ProviderUnavailable,
    RegistrationClosed,
    RegistrationRejected,
    SeatUnavailable,
    TicketNotFound,
)
from src.domain.seats import seat_in_pattern

logger = logging.getLogger(__name__)


class EventsProviderClient(typing.Protocol):
    async def seats(self, event_id: uuid.UUID) -> list[str]: ...

    async def register(
        self,
        event_id: uuid.UUID,
        first_name: str,
        last_name: str,
        email: str,
        seat: str,
    ) -> uuid.UUID: ...

    async def unregister(self, event_id: uuid.UUID, ticket_id: uuid.UUID) -> None: ...


class EventRepository(typing.Protocol):
    async def get(self, event_id: uuid.UUID) -> Event | None: ...


class TicketRepository(typing.Protocol):
    async def get(self, ticket_id: uuid.UUID) -> Ticket | None: ...

    async def save(self, ticket: Ticket) -> None: ...

    async def delete(self, ticket_id: uuid.UUID) -> None: ...


class SeatsCache(typing.Protocol):
    def delete(self, key: uuid.UUID) -> None: ...


class CreateTicketUsecase:
    def __init__(
        self,
        client: EventsProviderClient,
        events: EventRepository,
        tickets: TicketRepository,
        seats_cache: SeatsCache,
    ) -> None:
        self.client = client
        self.events = events
        self.tickets = tickets
        self.seats_cache = seats_cache

    async def do(
        self,
        event_id: uuid.UUID,
        first_name: str,
        last_name: str,
        email: str,
        seat: str,
    ) -> uuid.UUID:
        event = await self.events.get(event_id)
        if event is None:
            raise EventNotFound
        if event.status != EventStatus.PUBLISHED:
            raise EventNotPublished
        if datetime.now(UTC) >= event.registration_deadline:
            raise RegistrationClosed
        if not seat_in_pattern(seat, event.place.seats_pattern):
            raise InvalidSeat

        try:
            free_seats = await self.client.seats(event_id)
            if seat not in free_seats:
                raise SeatUnavailable
            ticket_id = await self.client.register(
                event_id, first_name, last_name, email, seat
            )
        except EventsProviderNotFound:
            raise EventNotFound from None
        except EventsProviderBadRequest as exc:
            # Someone may take the seat between our check and the registration.
            if "already sold" in exc.detail:
                raise SeatUnavailable from None
            raise RegistrationRejected(exc.detail) from None
        except (EventsProviderError, OSError) as exc:
            logger.warning("Registration for %s failed: %s", event_id, exc)
            raise ProviderUnavailable from exc
        finally:
            self.seats_cache.delete(event_id)

        await self.tickets.save(
            Ticket(
                id=ticket_id,
                event_id=event_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                seat=seat,
            )
        )
        logger.info("Registered ticket %s for event %s", ticket_id, event_id)
        return ticket_id


class CancelTicketUsecase:
    def __init__(
        self,
        client: EventsProviderClient,
        tickets: TicketRepository,
        seats_cache: SeatsCache,
    ) -> None:
        self.client = client
        self.tickets = tickets
        self.seats_cache = seats_cache

    async def do(self, ticket_id: uuid.UUID) -> None:
        ticket = await self.tickets.get(ticket_id)
        if ticket is None:
            raise TicketNotFound

        try:
            await self.client.unregister(ticket.event_id, ticket_id)
        except EventsProviderNotFound:
            # The provider no longer knows this ticket: drop our stale copy.
            await self.tickets.delete(ticket_id)
            raise TicketNotFound from None
        except EventsProviderBadRequest as exc:
            raise CancellationRejected(exc.detail) from None
        except (EventsProviderError, OSError) as exc:
            logger.warning("Cancellation of %s failed: %s", ticket_id, exc)
            raise ProviderUnavailable from exc
        finally:
            self.seats_cache.delete(ticket.event_id)

        await self.tickets.delete(ticket_id)
        logger.info("Cancelled ticket %s for event %s", ticket_id, ticket.event_id)
