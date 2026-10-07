import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, call

from src.clients.events_provider import (
    EventsPage,
    EventsPaginator,
    EventsProviderClient,
    ProviderEvent,
)
from tests.test_events_provider_client import make_event


def make_page(event_ids: list[str], next_cursor: str | None) -> EventsPage:
    return EventsPage(
        results=[ProviderEvent.model_validate(make_event(i)) for i in event_ids],
        next_cursor=next_cursor,
    )


IDS = [str(uuid.uuid4()) for _ in range(5)]


async def test_iterates_over_all_pages() -> None:
    client = MagicMock(spec=EventsProviderClient)
    client.events = AsyncMock(
        side_effect=[
            make_page(IDS[:2], "c1"),
            make_page(IDS[2:4], "c2"),
            make_page(IDS[4:], None),
        ]
    )

    events = [event async for event in EventsPaginator(client, date(2000, 1, 1))]

    assert [str(event.id) for event in events] == IDS
    assert client.events.await_args_list == [
        call(date(2000, 1, 1), None),
        call(date(2000, 1, 1), "c1"),
        call(date(2000, 1, 1), "c2"),
    ]


async def test_single_empty_page() -> None:
    client = MagicMock(spec=EventsProviderClient)
    client.events = AsyncMock(return_value=make_page([], None))

    events = [event async for event in EventsPaginator(client, date(2026, 1, 5))]

    assert events == []
    client.events.assert_awaited_once_with(date(2026, 1, 5), None)


async def test_pages_are_fetched_lazily() -> None:
    client = MagicMock(spec=EventsProviderClient)
    client.events = AsyncMock(
        side_effect=[make_page(IDS[:2], "c1"), make_page(IDS[2:], None)]
    )

    iterator = aiter(EventsPaginator(client, date(2000, 1, 1)))
    await anext(iterator)

    client.events.assert_awaited_once()
