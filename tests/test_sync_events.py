from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx

from src.clients.events_provider import EventsPage, ProviderEvent
from src.domain.entities import SyncState, SyncStatus
from src.usecases.sync_events import SyncEventsUsecase
from tests.test_events_provider_client import make_event


def provider_event(event_id: str, changed_at: str) -> ProviderEvent:
    data = make_event(event_id)
    data["changed_at"] = changed_at
    return ProviderEvent.model_validate(data)


E1 = provider_event("00000000-0000-0000-0000-000000000001", "2026-01-04T10:00:00+00:00")
E2 = provider_event("00000000-0000-0000-0000-000000000002", "2026-01-05T15:30:00+00:00")


def make_usecase(
    state: SyncState, pages: list[EventsPage]
) -> tuple[SyncEventsUsecase, MagicMock, MagicMock, MagicMock]:
    client = MagicMock()
    client.events = AsyncMock(side_effect=pages)
    events = MagicMock()
    events.upsert = AsyncMock()
    sync_state = MagicMock()
    sync_state.get = AsyncMock(return_value=state)
    sync_state.save = AsyncMock()
    return SyncEventsUsecase(client, events, sync_state), client, events, sync_state


async def test_first_sync_fetches_everything() -> None:
    usecase, client, events, sync_state = make_usecase(
        SyncState(),
        [
            EventsPage(results=[E2], next_cursor="c1"),
            EventsPage(results=[E1], next_cursor=None),
        ],
    )

    result = await usecase.do()

    assert client.events.await_args_list[0].args == (date(2000, 1, 1), None)
    assert events.upsert.await_count == 2
    assert result.status == SyncStatus.SUCCESS
    assert result.synced_events == 2
    saved: SyncState = sync_state.save.await_args.args[0]
    assert saved.sync_status == SyncStatus.SUCCESS
    assert saved.last_changed_at == E2.changed_at
    assert saved.last_sync_time is not None
    assert saved.error is None


async def test_incremental_sync_uses_last_changed_at() -> None:
    previous = datetime(2026, 1, 5, 15, 30, tzinfo=UTC)
    usecase, client, events, sync_state = make_usecase(
        SyncState(last_changed_at=previous, sync_status=SyncStatus.SUCCESS),
        [EventsPage(results=[], next_cursor=None)],
    )

    result = await usecase.do()

    client.events.assert_awaited_once_with(date(2026, 1, 5), None)
    events.upsert.assert_not_awaited()
    assert result.synced_events == 0
    assert sync_state.save.await_args.args[0].last_changed_at == previous


async def test_failure_keeps_last_changed_at_and_records_error() -> None:
    previous = datetime(2026, 1, 1, tzinfo=UTC)
    usecase, _, events, sync_state = make_usecase(
        SyncState(last_changed_at=previous),
        [EventsPage(results=[E2], next_cursor="c1"), httpx.ConnectError("down")],
    )

    result = await usecase.do()

    assert events.upsert.await_count == 1
    assert result.status == SyncStatus.FAILED
    saved: SyncState = sync_state.save.await_args.args[0]
    assert saved.sync_status == SyncStatus.FAILED
    assert saved.last_changed_at == previous
    assert saved.error == "down"
