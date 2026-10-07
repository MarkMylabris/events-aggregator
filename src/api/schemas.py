import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, PlainSerializer

from src.domain.entities import PROVIDER_TZ

ProviderDatetime = Annotated[
    datetime,
    PlainSerializer(lambda value: value.astimezone(PROVIDER_TZ).isoformat()),
]


class PlaceShort(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    address: str


class PlaceDetail(PlaceShort):
    seats_pattern: str


class EventShort(BaseModel):
    id: uuid.UUID
    name: str
    place: PlaceShort
    event_time: ProviderDatetime
    registration_deadline: ProviderDatetime
    status: str
    number_of_visitors: int


class EventDetail(EventShort):
    place: PlaceDetail


class EventsList(BaseModel):
    count: int
    next: str | None
    previous: str | None
    results: list[EventShort]


class Seats(BaseModel):
    event_id: uuid.UUID
    available_seats: list[str]
