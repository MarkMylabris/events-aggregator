import uuid
from dataclasses import asdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.api.dependencies import get_get_event_usecase, get_list_events_usecase
from src.api.schemas import EventDetail, EventShort, EventsList
from src.domain.exceptions import EventNotFound
from src.usecases.events import GetEventUsecase, ListEventsUsecase

router = APIRouter()


@router.get("/api/events", response_model=EventsList)
@router.get("/api/events/", response_model=EventsList, include_in_schema=False)
async def list_events(
    request: Request,
    usecase: Annotated[ListEventsUsecase, Depends(get_list_events_usecase)],
    date_from: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EventsList:
    result = await usecase.do(date_from, page, page_size)
    return EventsList(
        count=result.count,
        next=_page_url(request, page + 1) if result.has_next else None,
        previous=_page_url(request, page - 1) if result.has_previous else None,
        results=[EventShort.model_validate(asdict(e)) for e in result.results],
    )


@router.get("/api/events/{event_id}", response_model=EventDetail)
@router.get(
    "/api/events/{event_id}/", response_model=EventDetail, include_in_schema=False
)
async def get_event(
    event_id: uuid.UUID,
    usecase: Annotated[GetEventUsecase, Depends(get_get_event_usecase)],
) -> EventDetail:
    try:
        event = await usecase.do(event_id)
    except EventNotFound:
        raise HTTPException(status_code=404, detail="Event not found") from None
    return EventDetail.model_validate(asdict(event))


def _page_url(request: Request, page: int) -> str:
    return str(request.url.include_query_params(page=page))
