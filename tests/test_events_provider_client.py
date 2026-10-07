import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.clients.events_provider import (
    EventsProviderBadRequest,
    EventsProviderClient,
    EventsProviderError,
    EventsProviderNotFound,
)

BASE_URL = "http://provider"
EVENT_ID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
TICKET_ID = uuid.UUID("1fed0122-b675-42e2-8ae7-49bfb53e8d7f")


def make_event(event_id: str = str(EVENT_ID)) -> dict:
    return {
        "id": event_id,
        "name": "Конференция по Python",
        "place": {
            "id": "650e8400-e29b-41d4-a716-446655440001",
            "name": "Технопарк",
            "city": "Москва",
            "address": "ул. Ленина, д. 1",
            "seats_pattern": "A1-1000,B1-2000",
            "changed_at": "2025-01-01T03:00:00+03:00",
            "created_at": "2025-01-01T03:00:00+03:00",
        },
        "event_time": "2026-01-11T17:00:00+03:00",
        "registration_deadline": "2026-01-10T17:00:00+03:00",
        "status": "published",
        "number_of_visitors": 5,
        "changed_at": "2026-01-04T22:28:35.325270+03:00",
        "created_at": "2026-01-04T22:28:35.325302+03:00",
        "status_changed_at": "2026-01-04T22:28:35.325386+03:00",
    }


@pytest.fixture
def http() -> MagicMock:
    return MagicMock(spec=httpx.AsyncClient)


@pytest.fixture
def client(http: MagicMock) -> EventsProviderClient:
    return EventsProviderClient(BASE_URL, "secret", http=http, retry_delay=0)


async def test_events_requests_page_and_extracts_cursor(
    client: EventsProviderClient, http: MagicMock
) -> None:
    http.get = AsyncMock(
        return_value=httpx.Response(
            200,
            json={
                "next": f"{BASE_URL}/api/events/?changed_at=2000-01-01&cursor=abc",
                "previous": None,
                "results": [make_event()],
            },
        )
    )

    page = await client.events(date(2000, 1, 1))

    http.get.assert_awaited_once_with(
        f"{BASE_URL}/api/events/",
        headers={"x-api-key": "secret"},
        params={"changed_at": "2000-01-01"},
    )
    assert page.next_cursor == "abc"
    assert [event.id for event in page.results] == [EVENT_ID]
    assert page.results[0].place.city == "Москва"


async def test_events_passes_cursor_and_detects_last_page(
    client: EventsProviderClient, http: MagicMock
) -> None:
    http.get = AsyncMock(
        return_value=httpx.Response(
            200, json={"next": None, "previous": None, "results": []}
        )
    )

    page = await client.events(date(2026, 1, 5), cursor="abc")

    assert http.get.await_args.kwargs["params"] == {
        "changed_at": "2026-01-05",
        "cursor": "abc",
    }
    assert page.next_cursor is None
    assert page.results == []


async def test_seats_returns_list(
    client: EventsProviderClient, http: MagicMock
) -> None:
    http.get = AsyncMock(return_value=httpx.Response(200, json={"seats": ["A1"]}))

    seats = await client.seats(EVENT_ID)

    assert seats == ["A1"]
    assert http.get.await_args.args[0] == f"{BASE_URL}/api/events/{EVENT_ID}/seats/"


async def test_seats_not_found(client: EventsProviderClient, http: MagicMock) -> None:
    http.get = AsyncMock(
        return_value=httpx.Response(404, json={"detail": "Event not found"})
    )

    with pytest.raises(EventsProviderNotFound):
        await client.seats(EVENT_ID)


async def test_get_retries_on_transient_errors(
    client: EventsProviderClient, http: MagicMock
) -> None:
    http.get = AsyncMock(
        side_effect=[
            httpx.ConnectError("boom"),
            httpx.Response(503),
            httpx.Response(200, json={"seats": []}),
        ]
    )

    assert await client.seats(EVENT_ID) == []
    assert http.get.await_count == 3


async def test_get_gives_up_after_retries(
    client: EventsProviderClient, http: MagicMock
) -> None:
    http.get = AsyncMock(return_value=httpx.Response(503))

    with pytest.raises(EventsProviderError) as exc_info:
        await client.seats(EVENT_ID)

    assert exc_info.value.status_code == 503
    assert http.get.await_count == 3


async def test_register_returns_ticket_id(
    client: EventsProviderClient, http: MagicMock
) -> None:
    http.post = AsyncMock(
        return_value=httpx.Response(201, json={"ticket_id": str(TICKET_ID)})
    )

    ticket_id = await client.register(
        EVENT_ID, "Иван", "Иванов", "ivan@example.com", "A15"
    )

    assert ticket_id == TICKET_ID
    http.post.assert_awaited_once_with(
        f"{BASE_URL}/api/events/{EVENT_ID}/register/",
        headers={"x-api-key": "secret"},
        json={
            "first_name": "Иван",
            "last_name": "Иванов",
            "email": "ivan@example.com",
            "seat": "A15",
        },
    )


async def test_register_seat_taken_is_not_retried(
    client: EventsProviderClient, http: MagicMock
) -> None:
    http.post = AsyncMock(
        return_value=httpx.Response(
            400, json=["This ticket is not available (already sold)."]
        )
    )

    with pytest.raises(EventsProviderBadRequest, match="already sold"):
        await client.register(EVENT_ID, "Иван", "Иванов", "ivan@example.com", "A15")

    assert http.post.await_count == 1


async def test_unregister_sends_ticket_id(
    client: EventsProviderClient, http: MagicMock
) -> None:
    http.request = AsyncMock(return_value=httpx.Response(200, json={"success": True}))

    await client.unregister(EVENT_ID, TICKET_ID)

    http.request.assert_awaited_once_with(
        "DELETE",
        f"{BASE_URL}/api/events/{EVENT_ID}/unregister/",
        headers={"x-api-key": "secret"},
        json={"ticket_id": str(TICKET_ID)},
    )


async def test_unpublished_event_html_error(
    client: EventsProviderClient, http: MagicMock
) -> None:
    http.get = AsyncMock(
        return_value=httpx.Response(
            500, text="UnexpectedEventStatus: Event is not published"
        )
    )

    with pytest.raises(EventsProviderError) as exc_info:
        await client.seats(EVENT_ID)

    assert exc_info.value.status_code == 500
    assert http.get.await_count == 1
