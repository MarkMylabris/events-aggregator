from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.repositories.events import SqlEventRepository
from src.usecases.events import GetEventUsecase, ListEventsUsecase

Session = Annotated[AsyncSession, Depends(get_session)]


def get_event_repository(session: Session) -> SqlEventRepository:
    return SqlEventRepository(session)


EventRepositoryDep = Annotated[SqlEventRepository, Depends(get_event_repository)]


def get_list_events_usecase(events: EventRepositoryDep) -> ListEventsUsecase:
    return ListEventsUsecase(events)


def get_get_event_usecase(events: EventRepositoryDep) -> GetEventUsecase:
    return GetEventUsecase(events)
