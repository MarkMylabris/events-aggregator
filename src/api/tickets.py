from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_create_ticket_usecase
from src.api.schemas import TicketCreate, TicketCreated
from src.domain.exceptions import (
    EventNotFound,
    EventNotPublished,
    InvalidSeat,
    ProviderUnavailable,
    RegistrationClosed,
    RegistrationRejected,
    SeatUnavailable,
)
from src.usecases.tickets import CreateTicketUsecase

router = APIRouter()


@router.post("/api/tickets", status_code=201, response_model=TicketCreated)
@router.post(
    "/api/tickets/",
    status_code=201,
    response_model=TicketCreated,
    include_in_schema=False,
)
async def create_ticket(
    body: TicketCreate,
    usecase: Annotated[CreateTicketUsecase, Depends(get_create_ticket_usecase)],
) -> TicketCreated:
    try:
        ticket_id = await usecase.do(
            body.event_id, body.first_name, body.last_name, body.email, body.seat
        )
    except EventNotFound:
        raise HTTPException(404, "Event not found") from None
    except EventNotPublished:
        raise HTTPException(400, "Event is not published for registration") from None
    except RegistrationClosed:
        raise HTTPException(400, "Registration deadline has passed") from None
    except InvalidSeat:
        raise HTTPException(400, "Seat does not exist at this venue") from None
    except SeatUnavailable:
        raise HTTPException(400, "Seat is already taken") from None
    except RegistrationRejected as exc:
        raise HTTPException(400, f"Registration rejected: {exc}") from None
    except ProviderUnavailable:
        raise HTTPException(502, "Events Provider is unavailable") from None
    return TicketCreated(ticket_id=ticket_id)
