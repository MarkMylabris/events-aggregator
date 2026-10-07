from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_seats_usecase
from src.clients.events_provider import EventsProviderError, EventsProviderNotFound
from src.domain.exceptions import EventNotFound, EventNotPublished, ProviderUnavailable
from src.main import app
from src.services.cache import TTLCache
from src.usecases.seats import GetSeatsUsecase
from tests.test_events_api import make_event

EVENT = make_event(1)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_cache_expires_after_ttl() -> None:
    clock = FakeClock()
    cache = TTLCache(30, clock=clock)
    cache.set("key", ["A1"])

    clock.now = 29.9
    assert cache.get("key") == ["A1"]
    clock.now = 30
    assert cache.get("key") is None


def test_cache_delete() -> None:
    cache = TTLCache(30)
    cache.set("key", ["A1"])

    cache.delete("key")
    cache.delete("missing")

    assert cache.get("key") is None


def make_usecase(
    event=EVENT, seats=None, cache=None
) -> tuple[GetSeatsUsecase, MagicMock, MagicMock]:
    client = MagicMock()
    client.seats = AsyncMock(return_value=seats or ["A1", "A3"])
    events = MagicMock()
    events.get = AsyncMock(return_value=event)
    usecase = GetSeatsUsecase(client, events, cache or TTLCache(30))
    return usecase, client, events


async def test_seats_are_fetched_then_served_from_cache() -> None:
    usecase, client, _ = make_usecase()

    assert await usecase.do(EVENT.id) == ["A1", "A3"]
    assert await usecase.do(EVENT.id) == ["A1", "A3"]

    client.seats.assert_awaited_once_with(EVENT.id)


async def test_seats_are_refetched_after_ttl() -> None:
    clock = FakeClock()
    usecase, client, _ = make_usecase(cache=TTLCache(30, clock=clock))

    await usecase.do(EVENT.id)
    clock.now = 31
    await usecase.do(EVENT.id)

    assert client.seats.await_count == 2


async def test_unknown_event() -> None:
    usecase, client, _ = make_usecase(event=None)

    with pytest.raises(EventNotFound):
        await usecase.do(EVENT.id)
    client.seats.assert_not_awaited()


async def test_unpublished_event_is_not_sent_to_provider() -> None:
    usecase, client, _ = make_usecase(event=replace(EVENT, status="finished"))

    with pytest.raises(EventNotPublished):
        await usecase.do(EVENT.id)
    client.seats.assert_not_awaited()


async def test_provider_not_found() -> None:
    usecase, client, _ = make_usecase()
    client.seats.side_effect = EventsProviderNotFound(404, "Event not found")

    with pytest.raises(EventNotFound):
        await usecase.do(EVENT.id)


async def test_provider_failure_is_not_cached() -> None:
    usecase, client, _ = make_usecase()
    client.seats.side_effect = EventsProviderError(500, "boom")

    with pytest.raises(ProviderUnavailable):
        await usecase.do(EVENT.id)
    client.seats.side_effect = None
    assert await usecase.do(EVENT.id) == ["A1", "A3"]


@pytest.fixture
def seats_usecase() -> Iterator[MagicMock]:
    usecase = MagicMock()
    app.dependency_overrides[get_seats_usecase] = lambda: usecase
    yield usecase
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("error", "status"),
    [(EventNotFound, 404), (EventNotPublished, 400), (ProviderUnavailable, 502)],
)
def test_seats_endpoint_errors(
    seats_usecase: MagicMock, error: type[Exception], status: int
) -> None:
    seats_usecase.do = AsyncMock(side_effect=error)

    response = TestClient(app).get(f"/api/events/{EVENT.id}/seats")

    assert response.status_code == status


def test_seats_endpoint(seats_usecase: MagicMock) -> None:
    seats_usecase.do = AsyncMock(return_value=["A1", "A3"])

    response = TestClient(app).get(f"/api/events/{EVENT.id}/seats")

    assert response.status_code == 200
    assert response.json() == {
        "event_id": str(EVENT.id),
        "available_seats": ["A1", "A3"],
    }
