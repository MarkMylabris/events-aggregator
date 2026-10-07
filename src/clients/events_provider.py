import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime
from urllib.parse import parse_qs, urlparse

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

RETRY_STATUSES = {429, 502, 503, 504}


class ProviderPlace(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    address: str
    seats_pattern: str
    changed_at: datetime
    created_at: datetime


class ProviderEvent(BaseModel):
    id: uuid.UUID
    name: str
    place: ProviderPlace
    event_time: datetime
    registration_deadline: datetime
    status: str
    number_of_visitors: int
    changed_at: datetime
    created_at: datetime
    status_changed_at: datetime


class EventsPage(BaseModel):
    results: list[ProviderEvent]
    next_cursor: str | None


class EventsProviderError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"Events Provider error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class EventsProviderNotFound(EventsProviderError):
    pass


class EventsProviderBadRequest(EventsProviderError):
    pass


class EventsProviderClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        http: httpx.AsyncClient | None = None,
        retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=30)
        self._headers = {"x-api-key": api_key}
        self._retries = retries
        self._retry_delay = retry_delay

    async def close(self) -> None:
        await self._http.aclose()

    async def events(self, changed_at: date, cursor: str | None = None) -> EventsPage:
        params = {"changed_at": changed_at.isoformat()}
        if cursor:
            params["cursor"] = cursor
        data = await self._get("/api/events/", params=params)
        return EventsPage(
            results=data["results"],
            next_cursor=self._cursor_from_url(data["next"]),
        )

    async def seats(self, event_id: uuid.UUID) -> list[str]:
        data = await self._get(f"/api/events/{event_id}/seats/")
        return data["seats"]

    async def register(
        self,
        event_id: uuid.UUID,
        first_name: str,
        last_name: str,
        email: str,
        seat: str,
    ) -> uuid.UUID:
        response = await self._http.post(
            f"{self._base_url}/api/events/{event_id}/register/",
            headers=self._headers,
            json={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "seat": seat,
            },
        )
        self._raise_for_status(response)
        return uuid.UUID(response.json()["ticket_id"])

    async def unregister(self, event_id: uuid.UUID, ticket_id: uuid.UUID) -> None:
        response = await self._http.request(
            "DELETE",
            f"{self._base_url}/api/events/{event_id}/unregister/",
            headers=self._headers,
            json={"ticket_id": str(ticket_id)},
        )
        self._raise_for_status(response)

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict:
        # Only GET requests are retried: registration is not idempotent.
        for attempt in range(1, self._retries + 1):
            try:
                response = await self._http.get(
                    f"{self._base_url}{path}", headers=self._headers, params=params
                )
            except httpx.TransportError as exc:
                if attempt == self._retries:
                    raise
                logger.warning("GET %s failed (%s), retrying", path, exc)
            else:
                if response.status_code not in RETRY_STATUSES or (
                    attempt == self._retries
                ):
                    self._raise_for_status(response)
                    return response.json()
                logger.warning(
                    "GET %s returned %s, retrying", path, response.status_code
                )
            await asyncio.sleep(self._retry_delay * attempt)
        raise AssertionError("unreachable")

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        detail = response.text[:500]
        if response.status_code == 404:
            raise EventsProviderNotFound(response.status_code, detail)
        if response.status_code == 400:
            raise EventsProviderBadRequest(response.status_code, detail)
        raise EventsProviderError(response.status_code, detail)

    def _cursor_from_url(self, url: str | None) -> str | None:
        if not url:
            return None
        values = parse_qs(urlparse(url).query).get("cursor")
        return values[0] if values else None


class EventsPaginator:
    """Iterates over all events changed after ``changed_at``, page by page."""

    def __init__(self, client: EventsProviderClient, changed_at: date) -> None:
        self._client = client
        self._changed_at = changed_at

    def __aiter__(self) -> AsyncIterator[ProviderEvent]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[ProviderEvent]:
        cursor = None
        while True:
            page = await self._client.events(self._changed_at, cursor)
            for event in page.results:
                yield event
            if page.next_cursor is None:
                return
            cursor = page.next_cursor
