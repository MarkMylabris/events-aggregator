import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_seats_usecase
from src.api.schemas import Seats
from src.domain.exceptions import EventNotFound, EventNotPublished, ProviderUnavailable
from src.usecases.seats import GetSeatsUsecase

router = APIRouter()


@router.get("/api/events/{event_id}/seats", response_model=Seats)
@router.get(
    "/api/events/{event_id}/seats/", response_model=Seats, include_in_schema=False
)
async def get_seats(
    event_id: uuid.UUID,
    usecase: Annotated[GetSeatsUsecase, Depends(get_seats_usecase)],
) -> Seats:
    try:
        seats = await usecase.do(event_id)
    except EventNotFound:
        raise HTTPException(status_code=404, detail="Event not found") from None
    except EventNotPublished:
        raise HTTPException(
            status_code=400, detail="Event is not published for registration"
        ) from None
    except ProviderUnavailable:
        raise HTTPException(
            status_code=502, detail="Events Provider is unavailable"
        ) from None
    return Seats(event_id=event_id, available_seats=seats)
