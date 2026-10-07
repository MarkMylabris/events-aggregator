import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

# Events Provider works in Moscow time.
PROVIDER_TZ = timezone(timedelta(hours=3))


class EventStatus(StrEnum):
    NEW = "new"
    PUBLISHED = "published"


class SyncStatus(StrEnum):
    NEVER = "never"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class Place:
    id: uuid.UUID
    name: str
    city: str
    address: str
    seats_pattern: str
    changed_at: datetime
    created_at: datetime


@dataclass
class Event:
    id: uuid.UUID
    name: str
    place: Place
    event_time: datetime
    registration_deadline: datetime
    # Kept as a plain string: the provider has more statuses than documented.
    status: str
    number_of_visitors: int
    changed_at: datetime
    created_at: datetime
    status_changed_at: datetime


@dataclass
class SyncState:
    last_sync_time: datetime | None = None
    last_changed_at: datetime | None = None
    sync_status: str = SyncStatus.NEVER
    error: str | None = None


@dataclass
class Ticket:
    id: uuid.UUID
    event_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    seat: str
