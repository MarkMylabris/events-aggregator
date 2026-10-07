import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_create_ticket_usecase
from src.clients.events_provider import (
    EventsProviderBadRequest,
    EventsProviderError,
)
from src.domain.entities import Ticket
from src.domain.exceptions import (
    EventNotFound,
    EventNotPublished,
    InvalidSeat,
    ProviderUnavailable,
    RegistrationClosed,
    RegistrationRejected,
    SeatUnavailable,
)
from src.domain.seats import seat_in_pattern
from src.main import app
from src.usecases.tickets import CreateTicketUsecase
from tests.test_events_api import make_event

TICKET_ID = uuid.UUID("1fed0122-b675-42e2-8ae7-49bfb53e8d7f")
EVENT = replace(
    make_event(1),
    registration_deadline=datetime.now(UTC) + timedelta(days=1),
)
ARGS = (EVENT.id, "Иван", "Иванов", "ivan@example.com", "A15")


@pytest.mark.parametrize(
    ("seat", "expected"),
    [
        ("A1", True),
        ("A1000", True),
        ("B2000", True),
        ("A1001", False),
        ("A0", False),
        ("C1", False),
        ("a1", False),
        ("A", False),
    ],
)
def test_seat_in_pattern(seat: str, expected: bool) -> None:
    assert seat_in_pattern(seat, "A1-1000,B1-2000") is expected


def make_usecase(
    event=EVENT, free_seats=("A15",)
) -> tuple[CreateTicketUsecase, MagicMock, MagicMock, MagicMock]:
    client = MagicMock()
    client.seats = AsyncMock(return_value=list(free_seats))
    client.register = AsyncMock(return_value=TICKET_ID)
    events = MagicMock()
    events.get = AsyncMock(return_value=event)
    tickets = MagicMock()
    tickets.save = AsyncMock()
    cache = MagicMock()
    return CreateTicketUsecase(client, events, tickets, cache), client, tickets, cache


async def test_registers_and_saves_ticket() -> None:
    usecase, client, tickets, cache = make_usecase()

    ticket_id = await usecase.do(*ARGS)

    assert ticket_id == TICKET_ID
    client.register.assert_awaited_once_with(*ARGS)
    tickets.save.assert_awaited_once_with(
        Ticket(TICKET_ID, EVENT.id, "Иван", "Иванов", "ivan@example.com", "A15")
    )
    cache.delete.assert_called_once_with(EVENT.id)


@pytest.mark.parametrize(
    ("event", "error"),
    [
        (None, EventNotFound),
        (replace(EVENT, status="new"), EventNotPublished),
        (
            replace(EVENT, registration_deadline=datetime.now(UTC) - timedelta(1)),
            RegistrationClosed,
        ),
    ],
)
async def test_local_checks(event, error: type[Exception]) -> None:
    usecase, client, tickets, _ = make_usecase(event=event)

    with pytest.raises(error):
        await usecase.do(*ARGS)

    client.register.assert_not_awaited()
    tickets.save.assert_not_awaited()


async def test_seat_outside_pattern() -> None:
    usecase, client, _, _ = make_usecase()

    with pytest.raises(InvalidSeat):
        await usecase.do(EVENT.id, "Иван", "Иванов", "ivan@example.com", "Z1")

    client.seats.assert_not_awaited()


async def test_seat_already_taken() -> None:
    usecase, client, tickets, _ = make_usecase(free_seats=["A16"])

    with pytest.raises(SeatUnavailable):
        await usecase.do(*ARGS)

    client.register.assert_not_awaited()
    tickets.save.assert_not_awaited()


async def test_seat_taken_between_check_and_register() -> None:
    usecase, client, tickets, cache = make_usecase()
    client.register.side_effect = EventsProviderBadRequest(
        400, '["This ticket is not available (already sold)."]'
    )

    with pytest.raises(SeatUnavailable):
        await usecase.do(*ARGS)

    tickets.save.assert_not_awaited()
    cache.delete.assert_called_once_with(EVENT.id)


async def test_other_provider_rejection() -> None:
    usecase, client, _, _ = make_usecase()
    client.register.side_effect = EventsProviderBadRequest(400, "something else")

    with pytest.raises(RegistrationRejected, match="something else"):
        await usecase.do(*ARGS)


async def test_provider_down() -> None:
    usecase, client, tickets, _ = make_usecase()
    client.register.side_effect = EventsProviderError(503, "down")

    with pytest.raises(ProviderUnavailable):
        await usecase.do(*ARGS)

    tickets.save.assert_not_awaited()


@pytest.fixture
def ticket_usecase() -> Iterator[MagicMock]:
    usecase = MagicMock()
    usecase.do = AsyncMock(return_value=TICKET_ID)
    app.dependency_overrides[get_create_ticket_usecase] = lambda: usecase
    yield usecase
    app.dependency_overrides.clear()


BODY = {
    "event_id": str(EVENT.id),
    "first_name": " Иван ",
    "last_name": "Иванов",
    "email": "ivan@example.com",
    "seat": "A15",
}


def test_create_ticket_endpoint(ticket_usecase: MagicMock) -> None:
    response = TestClient(app).post("/api/tickets", json=BODY)

    assert response.status_code == 201
    assert response.json() == {"ticket_id": str(TICKET_ID)}
    ticket_usecase.do.assert_awaited_once_with(
        EVENT.id, "Иван", "Иванов", "ivan@example.com", "A15"
    )


@pytest.mark.parametrize(
    "override",
    [
        {"email": "not-an-email"},
        {"first_name": "   "},
        {"seat": "15A"},
        {"event_id": "nope"},
        {"last_name": None},
    ],
)
def test_create_ticket_validation(ticket_usecase: MagicMock, override: dict) -> None:
    response = TestClient(app).post("/api/tickets", json=BODY | override)

    assert response.status_code == 400
    ticket_usecase.do.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (EventNotFound, 404),
        (EventNotPublished, 400),
        (RegistrationClosed, 400),
        (InvalidSeat, 400),
        (SeatUnavailable, 400),
        (RegistrationRejected("x"), 400),
        (ProviderUnavailable, 502),
    ],
)
def test_create_ticket_errors(
    ticket_usecase: MagicMock, error: Exception, status: int
) -> None:
    ticket_usecase.do.side_effect = error

    response = TestClient(app).post("/api/tickets", json=BODY)

    assert response.status_code == status


def test_validation_error_lists_all_fields(ticket_usecase: MagicMock) -> None:
    body = BODY | {"event_id": "not-a-uuid", "email": "x"}

    response = TestClient(app).post("/api/tickets", json=body)

    assert response.status_code == 400
    fields = [error["loc"][-1] for error in response.json()["detail"]]
    assert fields == ["event_id", "email"]
