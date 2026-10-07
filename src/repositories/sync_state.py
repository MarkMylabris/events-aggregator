from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import SyncStateORM
from src.domain.entities import SyncState

# Sync metadata is a single row.
STATE_ID = 1


class SqlSyncStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> SyncState:
        row = await self.session.get(SyncStateORM, STATE_ID)
        if row is None:
            return SyncState()
        return SyncState(
            last_sync_time=row.last_sync_time,
            last_changed_at=row.last_changed_at,
            sync_status=row.sync_status,
            error=row.error,
        )

    async def save(self, state: SyncState) -> None:
        await self.session.merge(
            SyncStateORM(
                id=STATE_ID,
                last_sync_time=state.last_sync_time,
                last_changed_at=state.last_changed_at,
                sync_status=state.sync_status,
                error=state.error,
            )
        )
