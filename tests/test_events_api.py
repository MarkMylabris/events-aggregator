import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_event_repository
from src.domain.entities import PROVIDER_TZ, Event, Place
from src.main import app
from src.usecases.events import ListEventsUsecase

PLACE = Place(
    id=uuid.UUID("650e8400-e29b-41d4-a716-446655440001"),
    name="Технопарк",
    city="Москва",
    address="ул. Ленина, д. 1",
    seats_pattern="A1-1000,B1-2000",
    changed_at=datetime(2025, 1, 1, tzinfo=UTC),
    created_at=datetime(2025, 1, 1, tzinfo=UTC),
)


def make_event(n: int) -> Event:
    moment = datetime(2026, 1, 11, 14, tzinfo=UTC)
    return Event(
        id=uuid.UUID(int=n),
        name=f"Event {n}",
        place=PLACE,
        event_time=moment,
        registration_deadline=moment,
        status="published",
        number_of_visitors=5,
        changed_at=moment,
        created_at=moment,
        status_changed_at=moment,
    )


@pytest.fixture
def repository() -> Iterator[MagicMock]:
    repo = MagicMock()
    app.dependency_overrides[get_event_repository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_list_first_page(repository: MagicMock, client: TestClient) -> None:
    repository.count = AsyncMock(return_value=3)
    repository.list = AsyncMock(return_value=[make_event(1), make_event(2)])

    response = client.get("/api/events", params={"page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["previous"] is None
    assert body["next"] == "http://testserver/api/events?page_size=2&page=2"
    assert [e["name"] for e in body["results"]] == ["Event 1", "Event 2"]
    assert body["results"][0]["place"] == {
        "id": str(PLACE.id),
        "name": "Технопарк",
        "city": "Москва",
        "address": "ул. Ленина, д. 1",
    }
    repository.list.assert_awaited_once_with(None, 0, 2)


def test_list_last_page_with_date_filter(
    repository: MagicMock, client: TestClient
) -> None:
    repository.count = AsyncMock(return_value=3)
    repository.list = AsyncMock(return_value=[make_event(3)])

    response = client.get(
        "/api/events/", params={"date_from": "2026-01-10", "page": 2, "page_size": 2}
    )

    body = response.json()
    assert body["next"] is None
    assert body["previous"] == (
        "http://testserver/api/events/?date_from=2026-01-10&page_size=2&page=1"
    )
    since = datetime(2026, 1, 10, tzinfo=PROVIDER_TZ)
    repository.count.assert_awaited_once_with(since)
    repository.list.assert_awaited_once_with(since, 2, 2)


def test_list_rejects_bad_params(repository: MagicMock, client: TestClient) -> None:
    assert client.get("/api/events", params={"page": 0}).status_code == 422
    assert client.get("/api/events", params={"date_from": "x"}).status_code == 422


def test_event_detail(repository: MagicMock, client: TestClient) -> None:
    repository.get = AsyncMock(return_value=make_event(1))

    response = client.get(f"/api/events/{uuid.UUID(int=1)}")

    assert response.status_code == 200
    body = response.json()
    assert body["place"]["seats_pattern"] == "A1-1000,B1-2000"
    assert body["status"] == "published"


def test_event_detail_not_found(repository: MagicMock, client: TestClient) -> None:
    repository.get = AsyncMock(return_value=None)

    response = client.get(f"/api/events/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_list_usecase_without_filter() -> None:
    repository = MagicMock()
    repository.count = AsyncMock(return_value=40)
    repository.list = AsyncMock(return_value=[])

    page = await ListEventsUsecase(repository).do(None, 2, 20)

    repository.list.assert_awaited_once_with(None, 20, 20)
    assert page.has_previous
    assert not page.has_next


async def test_list_usecase_date_is_start_of_day() -> None:
    repository = MagicMock()
    repository.count = AsyncMock(return_value=0)
    repository.list = AsyncMock(return_value=[])

    await ListEventsUsecase(repository).do(date(2026, 1, 10), 1, 20)

    repository.count.assert_awaited_once_with(datetime(2026, 1, 10, tzinfo=PROVIDER_TZ))


def test_times_use_provider_offset(repository: MagicMock, client: TestClient) -> None:
    repository.get = AsyncMock(return_value=make_event(1))

    body = client.get(f"/api/events/{uuid.UUID(int=1)}").json()

    assert body["event_time"] == "2026-01-11T17:00:00+03:00"
