from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_cancel_ticket_usecase
from src.clients.events_provider import (
    EventsProviderBadRequest,
    EventsProviderError,
    EventsProviderNotFound,
)
from src.domain.entities import Ticket
from src.domain.exceptions import (
    CancellationRejected,
    ProviderUnavailable,
    TicketNotFound,
)
from src.main import app
from src.usecases.tickets import CancelTicketUsecase
from tests.test_tickets import EVENT, TICKET_ID

TICKET = Ticket(TICKET_ID, EVENT.id, "Иван", "Иванов", "ivan@example.com", "A15")


def make_usecase(
    ticket: Ticket | None = TICKET,
) -> tuple[CancelTicketUsecase, MagicMock, MagicMock, MagicMock]:
    client = MagicMock()
    client.unregister = AsyncMock()
    tickets = MagicMock()
    tickets.get = AsyncMock(return_value=ticket)
    tickets.delete = AsyncMock()
    cache = MagicMock()
    return CancelTicketUsecase(client, tickets, cache), client, tickets, cache


async def test_cancels_and_deletes_ticket() -> None:
    usecase, client, tickets, cache = make_usecase()

    await usecase.do(TICKET_ID)

    client.unregister.assert_awaited_once_with(EVENT.id, TICKET_ID)
    tickets.delete.assert_awaited_once_with(TICKET_ID)
    cache.delete.assert_called_once_with(EVENT.id)


async def test_unknown_ticket() -> None:
    usecase, client, _, _ = make_usecase(ticket=None)

    with pytest.raises(TicketNotFound):
        await usecase.do(TICKET_ID)

    client.unregister.assert_not_awaited()


async def test_ticket_unknown_to_provider_is_dropped() -> None:
    usecase, client, tickets, _ = make_usecase()
    client.unregister.side_effect = EventsProviderNotFound(404, "not found")

    with pytest.raises(TicketNotFound):
        await usecase.do(TICKET_ID)

    tickets.delete.assert_awaited_once_with(TICKET_ID)


async def test_provider_rejects_cancellation() -> None:
    usecase, client, tickets, _ = make_usecase()
    client.unregister.side_effect = EventsProviderBadRequest(400, "event is over")

    with pytest.raises(CancellationRejected, match="event is over"):
        await usecase.do(TICKET_ID)

    tickets.delete.assert_not_awaited()


async def test_provider_down_keeps_ticket() -> None:
    usecase, client, tickets, _ = make_usecase()
    client.unregister.side_effect = EventsProviderError(503, "down")

    with pytest.raises(ProviderUnavailable):
        await usecase.do(TICKET_ID)

    tickets.delete.assert_not_awaited()


@pytest.fixture
def cancel_usecase() -> Iterator[MagicMock]:
    usecase = MagicMock()
    usecase.do = AsyncMock()
    app.dependency_overrides[get_cancel_ticket_usecase] = lambda: usecase
    yield usecase
    app.dependency_overrides.clear()


def test_cancel_endpoint(cancel_usecase: MagicMock) -> None:
    response = TestClient(app).delete(f"/api/tickets/{TICKET_ID}")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    cancel_usecase.do.assert_awaited_once_with(TICKET_ID)


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (TicketNotFound, 404),
        (CancellationRejected("x"), 400),
        (ProviderUnavailable, 502),
    ],
)
def test_cancel_endpoint_errors(
    cancel_usecase: MagicMock, error: Exception, status: int
) -> None:
    cancel_usecase.do.side_effect = error

    response = TestClient(app).delete(f"/api/tickets/{TICKET_ID}")

    assert response.status_code == status


def test_cancel_endpoint_bad_id(cancel_usecase: MagicMock) -> None:
    assert TestClient(app).delete("/api/tickets/nope").status_code == 400
