import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, PlainSerializer, StringConstraints

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


Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class TicketCreate(BaseModel):
    event_id: uuid.UUID
    first_name: Name
    last_name: Name
    email: EmailStr
    seat: Annotated[str, Field(pattern=r"^[A-Z][1-9][0-9]*$", max_length=16)]


class TicketCreated(BaseModel):
    ticket_id: uuid.UUID
