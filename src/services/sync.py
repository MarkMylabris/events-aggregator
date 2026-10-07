import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.clients.events_provider import EventsProviderClient
from src.repositories.events import SqlEventRepository
from src.repositories.sync_state import SqlSyncStateRepository
from src.usecases.sync_events import SyncEventsUsecase, SyncResult

logger = logging.getLogger(__name__)

# Arbitrary key of the Postgres advisory lock that keeps replicas
# from syncing at the same time.
SYNC_LOCK_KEY = 815_001
SYNC_INTERVAL = timedelta(days=1)
CHECK_INTERVAL = timedelta(hours=1)


class SyncRunner:
    """Runs the sync use case in one transaction under an advisory lock."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        client: EventsProviderClient,
    ) -> None:
        self.session_factory = session_factory
        self.client = client

    async def run(self) -> SyncResult:
        async with self.session_factory() as session, session.begin():
            await session.execute(select(func.pg_advisory_xact_lock(SYNC_LOCK_KEY)))
            return await self._usecase(session).do()

    async def run_if_due(self) -> SyncResult | None:
        async with self.session_factory() as session, session.begin():
            locked = await session.scalar(
                select(func.pg_try_advisory_xact_lock(SYNC_LOCK_KEY))
            )
            if not locked:
                logger.info("Sync is running in another process, skipping")
                return None
            state = await SqlSyncStateRepository(session).get()
            if state.last_sync_time and (
                datetime.now(UTC) - state.last_sync_time < SYNC_INTERVAL
            ):
                return None
            return await self._usecase(session).do()

    async def run_forever(self) -> None:
        while True:
            try:
                await self.run_if_due()
            except Exception:
                logger.exception("Scheduled sync crashed")
            await asyncio.sleep(CHECK_INTERVAL.total_seconds())

    def _usecase(self, session: AsyncSession) -> SyncEventsUsecase:
        return SyncEventsUsecase(
            client=self.client,
            events=SqlEventRepository(session),
            sync_state=SqlSyncStateRepository(session),
        )
