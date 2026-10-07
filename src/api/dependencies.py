from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.repositories.events import SqlEventRepository
from src.repositories.tickets import SqlTicketRepository
from src.usecases.events import GetEventUsecase, ListEventsUsecase
from src.usecases.seats import GetSeatsUsecase
from src.usecases.tickets import CancelTicketUsecase, CreateTicketUsecase

Session = Annotated[AsyncSession, Depends(get_session)]


def get_event_repository(session: Session) -> SqlEventRepository:
    return SqlEventRepository(session)


EventRepositoryDep = Annotated[SqlEventRepository, Depends(get_event_repository)]


def get_list_events_usecase(events: EventRepositoryDep) -> ListEventsUsecase:
    return ListEventsUsecase(events)


def get_get_event_usecase(events: EventRepositoryDep) -> GetEventUsecase:
    return GetEventUsecase(events)


def get_seats_usecase(request: Request, events: EventRepositoryDep) -> GetSeatsUsecase:
    return GetSeatsUsecase(
        client=request.app.state.events_provider,
        events=events,
        cache=request.app.state.seats_cache,
    )


def get_create_ticket_usecase(
    request: Request, session: Session, events: EventRepositoryDep
) -> CreateTicketUsecase:
    return CreateTicketUsecase(
        client=request.app.state.events_provider,
        events=events,
        tickets=SqlTicketRepository(session),
        seats_cache=request.app.state.seats_cache,
    )


def get_cancel_ticket_usecase(
    request: Request, session: Session
) -> CancelTicketUsecase:
    return CancelTicketUsecase(
        client=request.app.state.events_provider,
        tickets=SqlTicketRepository(session),
        seats_cache=request.app.state.seats_cache,
    )
